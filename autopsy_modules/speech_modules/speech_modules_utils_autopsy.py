# Autopsy Speech to Text
# Copyright 2020 Miguel Negrao.

# Autopsy Speech to Text: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Autopsy Speech to Text is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Autopsy Speech to Text.  If not, see <http://www.gnu.org/licenses/>.

#java
import java.lang.System
from java.io import File
from java.util.logging import Level
from javax.swing import JComboBox, JLabel

from org.sleuthkit.autopsy.casemodule.services import Blackboard
from org.sleuthkit.autopsy.datamodel import ContentUtils
from org.sleuthkit.autopsy.casemodule import Case
from org.sleuthkit.datamodel import BlackboardArtifact
from org.sleuthkit.datamodel import BlackboardAttribute

from java.util.concurrent import Executors, Callable
from java.lang import Runtime

#python
import os
import subprocess
import wave
import codecs
import time

#note: changes in this file require restarting autopsy

class SubprocessError(Exception):

    def __init__(self, executable, errorCode, stderr):
        self.executable = executable
        self.errorCode = errorCode
        self.stderr = stderr
        self.message = executable + " failed with error code " + str(errorCode) + ".\nstderr: \n" + stderr

def execSubprocess(args, o, raiseException = True):
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if len(stdout) > 0:
                o.log(Level.INFO, args[0] + " stdout: \n" + stdout)
        if len(stderr) > 0:
                o.log(Level.INFO, args[0] + " stderr: \n" + stderr)
        if process.returncode != 0:
                o.log(Level.SEVERE, args[0] + "failed with error code " + str(process.returncode) + ".\n")
                if raiseException:
                        raise SubprocessError(args[0],  process.returncode, stderr)
        return (stdout, stderr)

def fileIsAudio(file):
    return (file.getMIMEType() is not None) and file.getMIMEType().startswith("audio")

def fileIsVideo(file):
    return (file.getMIMEType() is not None) and file.getMIMEType().startswith("video")

def osIsWindows():
        return java.lang.System.getProperty('os.name').startswith("Windows")

def getExecInModule(executableName):
    baseDir = os.path.dirname(os.path.realpath(__file__)) 
    return baseDir + "/bin/" + executableName + (".exe" if osIsWindows() else "")

def getExecInModuleIfInWindows(executableName):
        if osIsWindows():
                baseDir = os.path.dirname(os.path.realpath(__file__))
                return baseDir + "/bin/" + executableName + ".exe"
        else:
                return executableName

def copyToTempFile(file):
        root, ext = os.path.splitext(file.getName())
        tmpFilename =  root + "-" + str(file.getId()) + ext
        tempDir = Case.getCurrentCase().getTempDirectory()
        tmpPath = os.path.join(tempDir, tmpFilename)
        ContentUtils.writeToFile(file, File(tmpPath))
        return tmpPath

def convertAudioTo16kHzWav(file, tmpPath, logObj):
        convertFile = False
        if fileIsVideo(file):
                convertFile = True
        else:
                try:
                        wr = wave.open(tmpPath)
                        if wr.getsampwidth != 16 or wr.getframerate != 16000 or wr.getnchannels != 1:
                                convertFile = True
                #exception means it is not a WAV file
                except wave.Error:
                        convertFile = True
        if convertFile:
                tmpWav = tmpPath + ".wav"
                execSubprocess([
                        getExecInModuleIfInWindows("ffmpeg"),
                        '-y', '-i', tmpPath, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-vn', '-sn',
                        tmpWav,
                        ], logObj)
        return tmpWav

class RunFFMpeg(Callable):
    def __init__(self, file, tmpPath, logObj):
        self.file = file
        self.tmpPath = tmpPath
        self.logObj = logObj

    # needed to implement the Callable interface;
    # any exceptions will be wrapped as either ExecutionException
    # or InterruptedException
    def call(self):
        convertAudioTo16kHzWav(self.file, self.tmpPath, self.logObj)
        return self

def convertAudioFilesTo16kHzWav(list, logObj):
        pool = Executors.newFixedThreadPool(Runtime.getRuntime().availableProcessors())
        pool.invokeAll(map(lambda tuple: RunFFMpeg(tuple[0], tuple[1], logObj),list))
        pool.shutdownNow()

def avfileHasAudioStreams(audioFile, logObj):
        stdout, _ = execSubprocess([
                getExecInModuleIfInWindows("ffprobe"),
                "-show_streams", "-select_streams", "a", "-v", "0", "-of", "compact=p=0:nk=1",
                audioFile,
                ], logObj)
        return len(stdout) != 0

def getAVFileDuration(audioFile, logObj):
        stdout, _ = execSubprocess([
                            getExecInModuleIfInWindows("ffprobe"),
                            "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                            audioFile,
                            ], logObj)
        return float(stdout)



def runInaSpeechSegmener(files, obj):
        ina_clock_start = time.clock()
        execSubprocess([
                getExecInModule("ina_speech_segmenter/ina_speech_segmenter"),
                "-i"] + files + [
                "-o", Case.getCurrentCase().getTempDirectory() ], obj)
        ina_clock_end = time.clock()
        return ina_clock_end - ina_clock_start

def transcribeFiles(tmpAudioFiles, language, showTextSegmentStartTime, logObj):
        baseDir = os.path.dirname(os.path.realpath(__file__))
        args = [getExecInModule("deepspeech/deepspeech_csv"),
        "--model", baseDir + "/models/" + language + "/deepspeech.pbmm",
        "--scorer", baseDir + "/models/" + language + "/deepspeech.scorer"
        ] + ([] if showTextSegmentStartTime else ["--hide_segment_time"]) + tmpAudioFiles
        execSubprocess(args, logObj)

def importTranscribedTextFiles(fileWavPathPairs, obj, factory, tagsManager, tagTranscribed):
        results = []
        for file, wavFile in fileWavPathPairs:
                wavFileBase, _ = os.path.splitext(wavFile)
                txtFile = wavFileBase + ".txt"
                obj.log(Level.INFO, "importing text file: " + txtFile)
                try:
                        with codecs.open(txtFile, 'r', encoding="utf8") as txtFile2:
                                txtContent = txtFile2.read()
                                art = file.newArtifact(BlackboardArtifact.ARTIFACT_TYPE.TSK_EXTRACTED_TEXT)
                                att = BlackboardAttribute(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_TEXT, factory.moduleName, txtContent)
                                art.addAttribute(att)
                                indexArtifact(art, obj)
                                tagsManager.addContentTag(file, tagTranscribed)
                                results.append((file, txtContent))
                except:
                        obj.log(Level.INFO, "Could not open " + txtFile)
        return results

def makeLanguageSelectionComboBox(obj, value):
        modelsDir = os.path.dirname(os.path.realpath(__file__)) + "/models/"
        languages = []
        for root, _, _ in os.walk(modelsDir):
            if root != modelsDir:
                languages.append(os.path.split(root)[1])
        obj.add(JLabel("Language: "))
        combo = JComboBox(languages)
        combo.setSelectedItem(value)
        obj.add(combo)
        return combo

# index the artifact for keyword search
def indexArtifact(art, logObj):
        try:
                Case.getCurrentCase().getServices().getBlackboard().indexArtifact(art)
                logObj.log(Level.INFO, "Artifact indexed: " + art.getDisplayName())
        except:
                logObj.log(Level.SEVERE, "Error indexing artifact: " + art.getDisplayName())


def getOrAddTag(tagsManager, nameString):
        tagNames = tagsManager.getAllTagNames()
        tags = [tagName for tagName in tagNames if tagName.getDisplayName() == nameString ]
        return tagsManager.addTagName(nameString) if len(tags) == 0 else tags[0]