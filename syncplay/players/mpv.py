import re
import subprocess
from syncplay.players.mplayer import MplayerPlayer
from syncplay.messages import getMessage
from syncplay import constants
import os, sys, time

class MpvPlayer(MplayerPlayer):
    POSITION_QUERY = 'time-pos'
    OSD_QUERY = 'show_text'
    RE_VERSION = re.compile('.*mpv (\d)\.(\d)\.\d.*')

    def _setProperty(self, property_, value):
        self._listener.sendLine("no-osd set {} {}".format(property_, value))

    def setPaused(self, value):
        if self._paused <> value:
            self._paused = not self._paused
            self._listener.sendLine('cycle pause')

    def _storePosition(self, value):
        if self._resetPosition:
            self._position = 0
        elif self._fileIsLoaded():
            self._position = value
        else:
            self._position = self._client.getGlobalPosition()

    def _storePauseState(self, value):
        if self._fileIsLoaded():
            self._paused = value
        else:
            self._paused = self._client.getGlobalPaused()

    def _onFileUpdate(self):
        pass

    def _clearFileLoaded(self):
        self.fileLoaded = False
        self.lastLoadedTime = None

    def _loadFile(self, filePath):
        self._clearFileLoaded()
        self._listener.sendLine(u'loadfile {}'.format(self._quoteArg(filePath)))

    def _handleUnknownLine(self, line):
        if "Error parsing option" in line or "Error parsing commandline option" in line:
            self.quitReason = getMessage("mpv-version-error")

        elif line == "<SyncplayUpdateFile>":
            self._clearFileLoaded()

        elif line == "</SyncplayUpdateFile>":
            self._onMPVFileUpdate()

        elif "Failed to get value of property" in line:
            if "filename" in line:
                self._getFilename()
            elif "length" in line:
                self._getLength()
            elif "path" in line:
                self._getFilepath()
            elif "time-pos" in line:
                self.setPosition(self._client.getGlobalPosition())
                self._positionAsk.set()

        elif "Playing:" in line:
            if self._position < 1:
                self._resetPosition = True
            self._clearFileLoaded()

    def _onMPVFileUpdate(self):
        self.fileLoaded = True
        self.lastLoadedTime = time.time()
        self.reactor.callFromThread(self._client.updateFile, self._filename, self._duration, self._filepath)
        if not self._resetPosition:
            self.reactor.callFromThread(self.setPosition, self._client.getGlobalPosition())
        self._resetPosition = False
        if self._paused != self._client.getGlobalPaused():
            self.reactor.callFromThread(self._client.getGlobalPaused)

    def _fileIsLoaded(self):
        if self.fileLoaded == True and self.lastLoadedTime != None and time.time() > (self.lastLoadedTime + constants.MPV_NEWFILE_IGNORE_TIME):
            return True
        else:
            return False

    @staticmethod
    def run(client, playerPath, filePath, args):
        return MpvPlayer(client, MpvPlayer.getExpandedPath(playerPath), filePath, args)

    @staticmethod
    def getStartupArgs(path):
        try:
            ver = MpvPlayer.RE_VERSION.search(subprocess.check_output([path, '--version']))
        except:
            ver = None
        new_mpv = ver is None or int(ver.group(1)) > 0 or int(ver.group(2)) >= 5
        args = constants.MPV_SLAVE_ARGS
        if sys.platform.startswith('win') or not new_mpv:
             args.extend(constants.MPV_SLAVE_ARGS_WINDOWS)
        else:
             args.extend(constants.MPV_SLAVE_ARGS_NONWINDOWS)
        return args

    @staticmethod
    def getDefaultPlayerPathsList():
        l = []
        for path in constants.MPV_PATHS:
            p = MpvPlayer.getExpandedPath(path)
            if p:
                l.append(p)
        return l

    @staticmethod
    def isValidPlayerPath(path):
        if "mpv" in path and MpvPlayer.getExpandedPath(path):
            return True
        return False

    @staticmethod
    def getExpandedPath(playerPath):
        if not os.path.isfile(playerPath):
            if os.path.isfile(playerPath + u"mpv.exe"):
                playerPath += u"mpv.exe"
                return playerPath
            elif os.path.isfile(playerPath + u"\\mpv.exe"):
                playerPath += u"\\mpv.exe"
                return playerPath
        if os.access(playerPath, os.X_OK):
            return playerPath
        for path in os.environ['PATH'].split(':'):
            path = os.path.join(os.path.realpath(path), playerPath)
            if os.access(path, os.X_OK):
                return path

    @staticmethod
    def getIconPath(path):
        return constants.MPV_ICONPATH
