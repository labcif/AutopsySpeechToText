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

#Java
from java.lang import System
from java.io import File
from java.util.logging import Level
import java.lang.System
from javax.swing import JPanel, JComboBox, JLabel, BoxLayout, JRadioButton, ButtonGroup
from java.awt import GridLayout

from java.util.concurrent import Executors, Callable
from java.lang import Runtime

#Python
import os
import subprocess
import inspect
import platform
import wave
from mako.template import Template
import csv
import codecs
#import mako.template import Template

#Autopsy
from org.sleuthkit.autopsy.casemodule import Case
from org.sleuthkit.autopsy.report import GeneralReportModuleAdapter
from org.sleuthkit.autopsy.casemodule.services import TagsManager
from org.sleuthkit.autopsy.casemodule.services import Blackboard
from org.sleuthkit.autopsy.datamodel import ContentUtils
from org.sleuthkit.datamodel import BlackboardArtifact
from org.sleuthkit.datamodel import BlackboardAttribute
from org.sleuthkit.autopsy.coreutils import Logger
from org.sleuthkit.autopsy.report.ReportProgressPanel import ReportStatus
from org.sleuthkit.autopsy.ingest import IngestServices
from org.sleuthkit.autopsy.ingest import ModuleDataEvent

from speech_modules_utils_autopsy import * #getExecInModule, execSubprocess, copyToTempFile, fileIsVideo, makeLanguageSelectionComboBox

#html template for mako
htmlTemplate = """
<html>
  <head>
    <style>
    div.main {
        max-width:1000px;
        margin: auto;
    }
    </style>
    <title>My Python articles</title>
  </head>
  <body>
    <div class="main">
    <h1> Speech transcription report</h1>
    % for transcription in transcriptions:
        <h2>File: ${transcription[0]}</h2>
        <h2>Directory: ${transcription[1]}</h2>
        <ul>
        % for line in transcription[2]:
            <li>${line}</li>
        % endfor
        </ul>
    % endfor
    </div>
  </body>
</html>
"""

class RunProcessAVFileReport(Callable):
    def __init__(self, file, logObj):
        self.file = file
        self.logObj = logObj

    # needed to implement the Callable interface;
    # any exceptions will be wrapped as either ExecutionException
    # or InterruptedException
    def call(self):
        content = self.file.getContent()
        tmpPath = copyToTempFile(content)
        audioFilePath = convertAudioTo16kHzWav(content, tmpPath, self.logObj)
        return (content, audioFilePath)      


# TODO: Rename this to something more specific
class SpeechToTextReportModule(GeneralReportModuleAdapter):

    moduleName = "Speech to Text Report Module"

    _logger = None

    def log(self, level, msg):
        if self._logger == None:
            self._logger = Logger.getLogger(self.moduleName)

        self._logger.logp(level, self.__class__.__name__, inspect.stack()[1][3], msg)

    def getName(self):
        return self.moduleName

    # TODO: Give it a useful description
    def getDescription(self):
        return "Creates transcription of audio files tagged with \'Transcribe\' tag"

    # TODO: Update this to reflect where the report file will be written to
    def getRelativeFilePath(self):
        return "extracted-text." + ("html" if self.configPanel.radioButtonHTML.isSelected() else "csv")

    # The 'baseReportDir' object being passed in is a string with the directory that reports are being stored in.   Report should go into baseReportDir + getRelativeFilePath().
    # The 'progressBar' object is of type ReportProgressPanel.
    #   See: https://www.sleuthkit.org/autopsy/docs/api-docs/4.17.0/classorg_1_1sleuthkit_1_1autopsy_1_1report_1_1_report_progress_panel.html
    def generateReport(self, settings, progressBar):

        tagsManager = Case.getCurrentCase().getServices().getTagsManager()
        
        self.log(Level.INFO,"Starting ast report")
        
        tagTranscribe = getOrAddTag(tagsManager, "Transcribe")
        tagTranscribed = getOrAddTag(tagsManager, "Transcribed")
        
        tagToUse = tagTranscribed if self.configPanel.radioButtonTranscribed.isSelected() else tagTranscribe

        self.log(Level.INFO,"Using tag: " + str(tagToUse))

        #all files tagged tag to use
        #returns ContentTag: http://sleuthkit.org/sleuthkit/docs/jni-docs/4.6.0/classorg_1_1sleuthkit_1_1datamodel_1_1_content_tag.html
        # has method Content getContent ()
        # Content: http://sleuthkit.org/sleuthkit/docs/jni-docs/4.6.0/interfaceorg_1_1sleuthkit_1_1datamodel_1_1_content.html
        # in the ingest module an AbstractFile is used, which inherits from Content 
        files = tagsManager.getContentTagsByTagName(tagToUse)

        self.log(Level.INFO,"files: " + str(files))

        progressBar.setIndeterminate(False)
        progressBar.updateStatusLabel("Now processing files. \n\n This may take a long time.") 
        progressBar.start()
        progressBar.setMaximumProgress(3)

        fileName = os.path.join(settings.getReportDirectoryPath(), self.getRelativeFilePath())

        transcribedText = []


        if  self.configPanel.radioButtonTranscribed.isSelected():
            for file in files:
                content = file.getContent()
                artifacts = content.getArtifacts(BlackboardArtifact.ARTIFACT_TYPE.TSK_EXTRACTED_TEXT)
                firstArtifact = artifacts[0]
                outText = firstArtifact.getAttributes(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_TEXT)[0].getValueString()
                transcribedText.append([content.getName(), content.getParentPath(), outText.splitlines()])
        else:
            progressBar.updateStatusLabel("Running voice activity detection on " + str(len(files)) + " files. Be patient, this may take a while.")

            pool = Executors.newFixedThreadPool(Runtime.getRuntime().availableProcessors())
            futures = pool.invokeAll(map(lambda file: RunProcessAVFileReport(file, self), files))
            pool.shutdownNow()
            filesForDeepspeech = filter(lambda x: x is not None, map(lambda future: future.get(), futures))
            pathsForDeepspeech = map(lambda x: x[1], filesForDeepspeech)
            progressBar.increment()

            try:
                ina_run_time = runInaSpeechSegmener(pathsForDeepspeech, self)
                self.log(Level.INFO, "ina_speech_segmenter completed in " + str (ina_run_time) + "s")
                progressBar.updateStatusLabel("Transcribing " + str(len(files)) + " files. Be patient, this may take a while.")
                progressBar.increment()
                language = self.configPanel.combo.getSelectedItem()
                transcribeFiles(pathsForDeepspeech, language, True, self)
            except SubprocessError:
                self.log(Level.SEVERE, "Error transcribing files with deepspeech and inaSpeecSegmenter" )
                progressBar.cancel()
                return

            transcribedText0 = importTranscribedTextFiles(filesForDeepspeech, self, 
                    SpeechToTextReportModule, tagsManager,  tagTranscribed)

            # Fire an event to notify the UI and others that there is a new artifact
            # This will update the Results -> Extracted Content -> Extrected Text GUI item
            IngestServices.getInstance().fireModuleDataEvent(
                ModuleDataEvent(SpeechToTextReportModule.moduleName,
                BlackboardArtifact.ARTIFACT_TYPE.TSK_EXTRACTED_TEXT))

            transcribedText = map(lambda (file, text):
                [file.getName(), file.getParentPath(), text.splitlines()], transcribedText0)
                
        progressBar.increment()

        if self.configPanel.radioButtonHTML.isSelected():
            mytemplate = Template(htmlTemplate)
            with codecs.open(fileName, 'w', encoding='utf-8') as reportFile:
                reportFile.write(mytemplate.render(transcriptions=transcribedText))
            reportTitle = "Extracted text html"
        else:
            processedTranscribedText = map(lambda x: [x[0],x[1]," ".join(x[2]).replace("\n","")], transcribedText)
            processedTranscribedText = [["filename", "directory", "transcribed text"]] + processedTranscribedText
            self.log(Level.INFO, str(processedTranscribedText))
            with open(fileName, mode='wb') as reportFile:
                csv_writer = csv.writer(reportFile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                #deal with utf
                for row in processedTranscribedText:
                    csv_writer.writerows([[s.encode('utf-8') for s in row]])
            reportTitle = "Extracted text csv"
        
        Case.getCurrentCase().addReport(fileName, self.moduleName, reportTitle)
        progressBar.complete()
    
    def getConfigurationPanel(self):
        self.configPanel = SpeechToTextReport_ConfigPanel()
        return self.configPanel

class SpeechToTextReport_ConfigPanel(JPanel):

    def __init__(self):
        self.initComponents()
    
    def initComponents(self):

        self.panel = JPanel(GridLayout(0,1))
        self.combo = makeLanguageSelectionComboBox(self.panel, "english")
        
        #mode
        self.panel.add(JLabel("Choose mode: "))
        self.modeGroup = ButtonGroup()
        rb = JRadioButton
        self.radioButtonTranscribed = rb('Generate report of files with \'Transcribed\' tag.')
        radioButtons = (self.radioButtonTranscribed, rb('Transcribe files with \'Transcribe\' tag and generate report')) 
        for a_radiobutton in radioButtons:
            self.modeGroup.add(a_radiobutton)
            self.panel.add(a_radiobutton)
        self.radioButtonTranscribed.selected = 1

        #type
        self.panel.add(JLabel("Choose type: "))
        self.typeGroup = ButtonGroup()
        self.radioButtonHTML = rb('HTML')
        radioButtons = (self.radioButtonHTML, rb('CSV')) 
        for a_radiobutton in radioButtons:
            self.typeGroup.add(a_radiobutton)
            self.panel.add(a_radiobutton)
        self.radioButtonHTML.selected = 1

        self.add(self.panel)

        

 