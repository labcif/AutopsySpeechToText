# Sample module in the public domain. Feel free to use this as a template
# for your modules (and you can remove this header and take complete credit
# and liability)
#
# Contact: Brian Carrier [carrier <at> sleuthkit [dot] org]
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


# Ingest module for Autopsy with GUI
#
# Difference between other modules in this folder is that it has a GUI
# for user options.  This is not needed for very basic modules. If you
# don't need a configuration UI, start with the other sample module.
#
# Search for TODO for the things that you need to change
# See http://sleuthkit.org/autopsy/docs/api-docs/4.6.0/index.html for documentation


import jarray
import inspect
from java.lang import System
from java.util.logging import Level
from javax.swing import JCheckBox
from javax.swing import BoxLayout
from java.awt import GridLayout
from java.awt import Dimension
from java.awt.event import ActionListener
from javax.swing import JSlider
from javax.swing import JLabel

from org.sleuthkit.autopsy.casemodule import Case
from org.sleuthkit.autopsy.casemodule.services import Services
from org.sleuthkit.autopsy.ingest import DataSourceIngestModule
from org.sleuthkit.autopsy.ingest import FileIngestModule
from org.sleuthkit.autopsy.ingest import GenericIngestModuleJobSettings
from org.sleuthkit.autopsy.ingest import IngestMessage
from org.sleuthkit.autopsy.ingest import IngestModule
from org.sleuthkit.autopsy.ingest.IngestModule import IngestModuleException
from org.sleuthkit.autopsy.ingest import IngestModuleFactoryAdapter
from org.sleuthkit.autopsy.ingest import IngestModuleIngestJobSettings
from org.sleuthkit.autopsy.ingest import IngestModuleIngestJobSettingsPanel
from org.sleuthkit.autopsy.ingest import IngestServices
from org.sleuthkit.autopsy.ingest import IngestModuleGlobalSettingsPanel
from org.sleuthkit.datamodel import BlackboardArtifact
from org.sleuthkit.datamodel import BlackboardAttribute
from org.sleuthkit.datamodel import ReadContentInputStream
from org.sleuthkit.autopsy.coreutils import Logger
from java.lang import IllegalArgumentException


import jarray
import inspect
from java.lang import System
from java.util.logging import Level
from java.io import File
from javax.swing import JCheckBox
from javax.swing import JSlider
from javax.swing import BoxLayout
from java.lang import IllegalArgumentException

from org.sleuthkit.datamodel import SleuthkitCase
from org.sleuthkit.datamodel import AbstractFile
from org.sleuthkit.datamodel import ReadContentInputStream
from org.sleuthkit.datamodel import BlackboardArtifact
from org.sleuthkit.datamodel import BlackboardAttribute
from org.sleuthkit.datamodel import TskData
from org.sleuthkit.autopsy.ingest import IngestModule
from org.sleuthkit.autopsy.ingest.IngestModule import IngestModuleException
from org.sleuthkit.autopsy.ingest import DataSourceIngestModule
from org.sleuthkit.autopsy.ingest import FileIngestModule
from org.sleuthkit.autopsy.ingest import GenericIngestModuleJobSettings
from org.sleuthkit.autopsy.ingest import IngestModuleFactoryAdapter
from org.sleuthkit.autopsy.ingest import IngestModuleIngestJobSettings
from org.sleuthkit.autopsy.ingest import IngestModuleIngestJobSettingsPanel
from org.sleuthkit.autopsy.ingest import IngestModuleGlobalSettingsPanel
from org.sleuthkit.autopsy.ingest import IngestMessage
from org.sleuthkit.autopsy.ingest import IngestServices
from org.sleuthkit.autopsy.ingest import ModuleDataEvent
from org.sleuthkit.autopsy.datamodel import ContentUtils
from org.sleuthkit.autopsy.coreutils import Logger
from org.sleuthkit.autopsy.casemodule import Case
from org.sleuthkit.autopsy.casemodule.services import Services
from org.sleuthkit.autopsy.casemodule.services import FileManager
from org.sleuthkit.autopsy.casemodule.services import Blackboard    
from org.sleuthkit.autopsy.casemodule.services import TagsManager

import os
import subprocess

#delete
import time

from speech_modules_utils_autopsy import * #SubprocessError, getExecInModule, copyToTempFile, fileIsAudio, fileIsVideo, execSubprocess, getExecInModuleIfInWindows, transcribeFile, makeLanguageSelectionComboBox
from process_inaSpeechSegmenter import processInaSpeechSegmenterCSV

minPercVoicedDefault = 10
minTotalVoicedDefault = 10
runVadTranscriberDefault = False
showTextSegmentStartTimeDefault = True
vadTranscriberLanguage = "english"

def stringSettingsToObject(stringSettings):
    return VADSettings(
        int(stringSettings.getSetting("minPercVoiced")),
        int(stringSettings.getSetting("minTotalVoiced")),
        eval(stringSettings.getSetting("runVadTranscriber")),
        eval(stringSettings.getSetting("showTextSegmentStartTime")),
        stringSettings.getSetting("vadTranscriberLanguage"))

class VADSettings:
    def __init__(self, minPercVoiced, minTotalVoiced, runVadTranscriber, showTextSegmentStartTime, vadTranscriberLanguage):
        self.minPercVoiced = minPercVoiced
        self.minTotalVoiced = minTotalVoiced
        self.runVadTranscriber = runVadTranscriber
        self.showTextSegmentStartTime = showTextSegmentStartTime
        self.vadTranscriberLanguage = vadTranscriberLanguage

class VadCheckModuleFactory(IngestModuleFactoryAdapter):
    def __init__(self):
        self.settings = None

    # TODO: give it a unique name.  Will be shown in module list, logs, etc.
    moduleName = "Voice Activity Detection"

    def getModuleDisplayName(self):
        return self.moduleName

    # TODO: Give it a description
    def getModuleDescription(self):
        return "Detects the presence of human speech in audio files."

    def getModuleVersionNumber(self):
        return "1.0"

    # TODO: Update class name to one that you create below
    def getDefaultIngestJobSettings(self):
        s = GenericIngestModuleJobSettings()
        s.setSetting("minPercVoiced", str(minPercVoicedDefault))
        s.setSetting("minTotalVoiced", str(minTotalVoicedDefault))
        s.setSetting("runVadTranscriber", str(runVadTranscriberDefault))
        s.setSetting("showTextSegmentStartTime", str(showTextSegmentStartTimeDefault))
        return s

    # TODO: Keep enabled only if you need ingest job-specific settings UI
    def hasIngestJobSettingsPanel(self):
        return True

    # TODO: Update class names to ones that you create below
    # Note that you must use GenericIngestModuleJobSettings instead of making a custom settings class.
    def getIngestJobSettingsPanel(self, settings):
        if not isinstance(settings, GenericIngestModuleJobSettings):
            raise IllegalArgumentException("Expected settings argument to be instanceof GenericIngestModuleJobSettings")
        self.settings = settings
        return VadCheckModuleSettingsPanel(self.settings)

    def isDataSourceIngestModuleFactory(self):
        return True

    # TODO: Update class name to one that you create below
    def createDataSourceIngestModule(self, ingestOptions):
        return VadCheckModule(self.settings)


# File-level ingest module.  One gets created per thread.
# TODO: Rename this to something more specific. Could just remove "Factory" from above name.
# Looks at the attributes of the passed in file.
class VadCheckModule(DataSourceIngestModule):

    _logger = Logger.getLogger(VadCheckModuleFactory.moduleName)

    def log(self, level, msg):
        self._logger.logp(level, self.__class__.__name__, inspect.stack()[1][3], msg)

    # Autopsy will pass in the settings from the UI panel
    def __init__(self, settings):
        self.local_settings = stringSettingsToObject(settings)

    # Where any setup and configuration is done
    # TODO: Add any setup code that you need here.
    def startUp(self, context):
        # As an example, determine if user configured a flag in UI
        #if self.local_settings.getSetting("flag") == "true":
        #    self.log(Level.INFO, "flag is set")
        #else:
        #    self.log(Level.INFO, "flag is not set")
        #self.filesFound = 0
        # Throw an IngestModule.IngestModuleException exception if there was a problem setting up
        # raise IngestModuleException("Oh No!")
        pass

    # Where the analysis is done.  Each file will be passed into here.
    # TODO: Add your analysis code in here.
    def process(self, dataSource, progressBar):
        
        def addArtifact(file, message):
            art = file.newArtifact(BlackboardArtifact.ARTIFACT_TYPE.TSK_INTERESTING_FILE_HIT)
            att = BlackboardAttribute(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_SET_NAME,
                    VadCheckModuleFactory.moduleName, message)
            art.addAttribute(att)

        start = time.clock()

        # get or create "Transcribed" tag
        tagsManager = Case.getCurrentCase().getServices().getTagsManager()
        tagTranscribed = getOrAddTag(tagsManager, "Transcribed")

        self.log(Level.INFO, "Starting vad_check_ingest with settings minPercVoiced " + str(self.local_settings.minPercVoiced) + 
                " minTotalVoiced " + str(self.local_settings.minTotalVoiced))

        progressBar.switchToIndeterminate()
        fileManager = Case.getCurrentCase().getServices().getFileManager()
        #get all files
        files = fileManager.findFiles(dataSource, "%")
        numFiles = len(files)
        self.log(Level.INFO, "found " + str(numFiles) + " files")
        progressBar.switchToDeterminate(numFiles)

        filesForVoiceClassification = []
        fileCount = 0
        for file in files:
            try:
                self.log(Level.INFO, "Processing file: " + file.getName())
                progressBar.progress(file.getName())
                fileCount += 1
                progressBar.progress(fileCount)
                
                # Skip non-files
                if ((file.getType() != TskData.TSK_DB_FILES_TYPE_ENUM.UNALLOC_BLOCKS) and
                    (file.getType() != TskData.TSK_DB_FILES_TYPE_ENUM.UNUSED_BLOCKS) and
                    (file.isFile()) and
                    (fileIsAudio(file) or fileIsVideo(file))):

                    self.log(Level.INFO, "Found an audio/video file: " + file.getName())
                    
                    tmpFile = copyToTempFile(file)

                    #check if audio/video file has audio streams
                    if not avfileHasAudioStreams(tmpFile, self):
                        self.log(Level.INFO, "audio/video file with no audio streams: " + file.getName() )
                        addArtifact(file, "audio/video file with no audio stream")

                    #get duration of audio/video file
                    duration = getAVFileDuration(tmpFile, self)
                    self.log(Level.INFO, file.getName() + " has duration " + str(duration))

                    if (duration < self.local_settings.minTotalVoiced):
                        self.log(Level.INFO, "Audio file " + file.getName() + " too short.")
                        addArtifact(file, "duration too short")
                        continue

                    #convert audio/video file to wav file 16bit at 16kHz
                    tmpWav = convertAudioTo16kHzWav(file, tmpFile, self)

                    filesForVoiceClassification.append((file, tmpWav))
            except SubprocessError:
                continue

        if len(filesForVoiceClassification) == 0:
            return IngestModule.ProcessResult.OK

        tmpFiles = map(lambda x: x[1], filesForVoiceClassification)
        self.log(Level.INFO, "Files to classify speech/not speech:\n" + "\n".join(tmpFiles))
        progressBar.switchToIndeterminate()
        #now run all files of interest through ina_speech_segmenter to detect voice activity
#TODO remove call to fmpeg from ina_speech_segmenter
        try:
            ina_clock_start = time.clock()
            execSubprocess([
                getExecInModule("ina_speech_segmenter"),
                "-i"] + tmpFiles + [
                "-o", Case.getCurrentCase().getTempDirectory() ], self)
            ina_clock_end = time.clock()
            self.log(Level.INFO, "ina_speech_segmenter completed in " + str(ina_clock_end-ina_clock_start) + "s")
        except SubprocessError:
            for file, tmpFile in filesForVoiceClassification:
                addArtifact(file, "error")

        progressBar.switchToDeterminate(len(filesForVoiceClassification))
        
        for file, tmpFile in filesForVoiceClassification:
            tmpFileBase, _ = os.path.splitext(tmpFile)
            csvFile = tmpFileBase + ".csv"
            total_voiced, total_female, total_male = processInaSpeechSegmenterCSV(csvFile)
            perc_voiced_frames = total_voiced / duration * 100

            if ((perc_voiced_frames > self.local_settings.minPercVoiced ) and
                    (total_voiced > self.local_settings.minTotalVoiced)):
                self.log(Level.INFO, "Found an audio file with speech: " + file.getName())         
                
                addArtifact(file, "Audio files with speech")    
                if total_male > 0:
                    addArtifact(file, "Audio files with speech - male")
                if total_female > 0:
                    addArtifact(file, "Audio files with speech - female")

                if self.local_settings.runVadTranscriber:
                    try:
                        transcribeFile(file, tmpFile, self.local_settings.vadTranscriberLanguage, self.local_settings.showTextSegmentStartTime, self, VadCheckModuleFactory.moduleName)
                        tagsManager.addContentTag(file, tagTranscribed)
                    except SubprocessError:
                        continue
            else:
                self.log(Level.INFO, "Audio file " + file.getName() + "doesn't match conditions. perc_voiced_frames = " + str(perc_voiced_frames)+
                    "total_voiced = " + str(total_voiced))
                addArtifact(file, "not respecting conditions")

            # Fire an event to notify the UI and others that there is a new artifact
            IngestServices.getInstance().fireModuleDataEvent(
                ModuleDataEvent(VadCheckModuleFactory.moduleName,
                    BlackboardArtifact.ARTIFACT_TYPE.TSK_INTERESTING_FILE_HIT, None))
            progressBar.progress(fileCount)
			
        end = time.clock()
        self.log(Level.INFO, "Vad_check_ingest completed in " + str(end-start) + "s")
        return IngestModule.ProcessResult.OK

    # Where any shutdown code is run and resources are freed.
    # TODO: Add any shutdown code that you need here.
    def shutDown(self):
        pass


# UI that is shown to user for each ingest job so they can configure the job.
class VadCheckModuleSettingsPanel(IngestModuleIngestJobSettingsPanel):
    # Note, we can't use a self.settings instance variable.
    # Rather, self.local_settings is used.
    # https://wiki.python.org/jython/UserGuide#javabean-properties
    # Jython Introspector generates a property - 'settings' on the basis
    # of getSettings() defined in this class. Since only getter function
    # is present, it creates a read-only 'settings' property. This auto-
    # generated read-only property overshadows the instance-variable -
    # 'settings'

    # We get passed in a previous version of the settings so that we can
    # prepopulate the UI
    # TODO: Update this for your UI
    def __init__(self, settings):
        #print("init: " + settings.getSetting("runVadTranscriber") + " " + settings.getSetting("minPercVoiced") + " " + settings.getSetting("minTotalVoiced"))
        #print("init local_settings: " + self.local_settings.getSetting("vadAggressivness") + " " + self.local_settings.getSetting("minPercVoiced") + " " + self.local_settings.getSetting("minTotalVoiced"))
        self.local_settings = GenericIngestModuleJobSettings()
        #initComponents will initialize sliders which will call lambdas for updating settings using current values in sliders
        #which would overwrite settings.
        self.initComponents()
        #print("init local_settings 2: " + self.local_settings.getSetting("vadAggressivness") + " " + self.local_settings.getSetting("minPercVoiced") + " " + self.local_settings.getSetting("minTotalVoiced"))
        #now safe to set settings
        self.local_settings = settings
        #print("init 2: " + self.local_settings.getSetting("runVadTranscriber") + " " + self.local_settings.getSetting("minPercVoiced") + " " + self.local_settings.getSetting("minTotalVoiced"))
        self.customizeComponents()
    
    _logger = Logger.getLogger(VadCheckModuleFactory.moduleName)

    def log(self, level, msg):
        self._logger.logp(level, self.__class__.__name__, inspect.stack()[1][3], msg)

    # def makeGuiCallback(self, key, guiGetAction):
    #     def callback(event):
    #         #self.log(Level.INFO, "setting key = " + key + " val =" + str(event.getSource().getValue()))
    #         value = str(guiGetAction(event.getSource()))
    #         print("setting key = " + key + " val =" + value)
    #         self.local_settings.setSetting(key, value)
    #         print("test in settings key = " + key + " val =" + self.local_settings.getSetting(key))
    #     return callback    

    def initComponents(self):
        #print("initComponents 1: " + self.local_settings.getSetting("vadAggressivness") + " " + self.local_settings.getSetting("minPercVoiced") + " " + self.local_settings.getSetting("minTotalVoiced"))
        self.setLayout(BoxLayout(self, BoxLayout.Y_AXIS))

        self.label2 = JLabel()
        self.label2.setText("Minimum percentage voiced frames")
        self.label3 = JLabel()
        self.label3.setText("Minimum total duration of voiced frames (s)")

        #sliderGetAction = lambda slider: slider.getValue()
        self.minPercVoiced = JSlider()#stateChanged=self.makeGuiCallback("minPercVoiced", sliderGetAction))
        self.minPercVoiced.setMajorTickSpacing(20)
        self.minPercVoiced.setMinorTickSpacing(5)
        self.minPercVoiced.setPaintLabels(True)
        self.minPercVoiced.setPaintTicks(True)

        self.minTotalVoiced = JSlider()#stateChanged=self.makeGuiCallback("minTotalVoiced", sliderGetAction))
        self.minTotalVoiced.setMajorTickSpacing(60)
        self.minTotalVoiced.setMaximum(180)
        self.minTotalVoiced.setMinorTickSpacing(10)
        self.minTotalVoiced.setPaintLabels(True)
        self.minTotalVoiced.setPaintTicks(True)
        #print("initComponents 2: " + self.local_settings.getSetting("vadAggressivness") + " " + self.local_settings.getSetting("minPercVoiced") + " " + self.local_settings.getSetting("minTotalVoiced"))

        #checkboxGetAction = lambda checkbox: checkbox.isSelected()
        self.runVadTranscriber = JCheckBox("Transcribe files with speech detected ? (slow)")#,
            #actionPerformed=self.makeGuiCallback("runVadTranscriber", checkboxGetAction))
        self.showTextSegmentStartTime = JCheckBox("Show text segment start time ?")

        self.add(self.label2)
        self.add(self.minPercVoiced)
        self.add(self.label3)
        self.add(self.minTotalVoiced)
        self.add(self.showTextSegmentStartTime)
        self.add(self.runVadTranscriber)

        self.vadTranscriberLanguage = makeLanguageSelectionComboBox(self, "english")
        #this is needed because of https://bugs.jython.org/issue1749824
        #class ComboActionListener(ActionListener):
        #    def actionPerformed(self, e):
        #        value = e.getSource().getSelectedItem()
        #        self.local_settings.setSetting(key, value)

        #self.vadTranscriberLanguage.actionListener = ComboActionListener()

    #local_settings is of type https://github.com/sleuthkit/autopsy/blob/bbdea786db487c781edf2cf9032a2ba3166e97e0/Core/src/org/sleuthkit/autopsy/ingest/GenericIngestModuleJobSettings.java
    def customizeComponents(self):
        def setValue(key, default, stringToPythonObj, guiSetAction):
            string = self.local_settings.getSetting(key)
            #print("customizeComponents " + key + " stored value was " + str(string))
            #print("string is None " + str(string is None) + " stringToPythonObj(string) " + str(stringToPythonObj(string)))
            checkedValue = default if string is None else stringToPythonObj(string)
            obj = getattr(self, key)
            guiSetAction(obj, checkedValue)
            #self.log(Level.INFO, "setValue for key " + key + " " + str(checkedValue))
        
        sliderSetAction = lambda obj, val: obj.setValue(val)
        checkBoxSetAction = lambda obj, val: obj.setSelected(val)
        comboBoxSetAction = lambda obj, val: obj.setSelectedItem(val)

        setValue("minPercVoiced", minPercVoicedDefault, int, sliderSetAction)
        setValue("minTotalVoiced", minTotalVoicedDefault, int, sliderSetAction)
        setValue("runVadTranscriber", runVadTranscriberDefault, eval, checkBoxSetAction)
        setValue("showTextSegmentStartTime", showTextSegmentStartTimeDefault, eval, checkBoxSetAction)
        setValue("vadTranscriberLanguage", runVadTranscriberDefault, lambda x: x, comboBoxSetAction)

    # Return the settings used
    #note: exceptions thrown here will be caught and not logged.
    def getSettings(self):
        #print("getSettings: " + self.local_settings.getSetting("runVadTranscriber") + " " + self.local_settings.getSetting("minPercVoiced") + " " + self.local_settings.getSetting("minTotalVoiced"))
        
        self.local_settings.setSetting("minPercVoiced", str(self.minPercVoiced.getValue()))
        self.local_settings.setSetting("minTotalVoiced", str(self.minTotalVoiced.getValue()))
        self.local_settings.setSetting("runVadTranscriber", str(self.runVadTranscriber.isSelected()))
        self.local_settings.setSetting("showTextSegmentStartTime", str(self.showTextSegmentStartTime.isSelected()))
        self.local_settings.setSetting("vadTranscriberLanguage", str(self.vadTranscriberLanguage.getSelectedItem()))
 
        return self.local_settings

