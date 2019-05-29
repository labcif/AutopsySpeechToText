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


# Report module for Autopsy.
#
# Search for TODO for the things that you need to change
# See http://sleuthkit.org/autopsy/docs/api-docs/3.1/index.html for documentation

#Java
from java.lang import System
from java.io import File
from java.util.logging import Level
import java.lang.System
from javax.swing import JPanel, JComboBox, JLabel, BoxLayout, JRadioButton, ButtonGroup
from java.awt import GridLayout

#Python
import os
import subprocess
import inspect
import platform
import wave
from mako.template import Template
import csv
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
    #   See: http://sleuthkit.org/autopsy/docs/api-docs/4.6.0/classorg_1_1sleuthkit_1_1autopsy_1_1report_1_1_report_progress_panel
    def generateReport(self, settings, progressBar):

            tagsManager = Case.getCurrentCase().getServices().getTagsManager()
            
            self.log(Level.INFO,"Starting ast report")
           
            tagTranscribe = getOrAddTag(tagsManager, "Transcribe")
            tagTranscribed = getOrAddTag(tagsManager, "Transcribed")
            
            tagToUse = tagTranscribed if self.configPanel.radioButtonTranscribed.isSelected() else tagTranscribe

            self.log(Level.INFO,"Using tag: " + str(tagToUse))

            #all files tagged tag to use
            files = tagsManager.getContentTagsByTagName(tagToUse)

            self.log(Level.INFO,"files: " + str(files))

            progressBar.setIndeterminate(False)
            progressBar.updateStatusLabel("Now processing files. \n\n This may take a long time.") 
            progressBar.start()
            progressBar.setMaximumProgress(files.size())

            fileName = os.path.join(settings.getReportDirectoryPath(), self.getRelativeFilePath())

            transcribedText = []

            for file in files:
                try:
                    content = file.getContent()

                    if  self.configPanel.radioButtonTranscribed.isSelected():
                        artifacts = content.getArtifacts(BlackboardArtifact.ARTIFACT_TYPE.TSK_EXTRACTED_TEXT)
                        firstArtifact = artifacts[0]
                        outText = firstArtifact.getAttributes(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_TEXT)[0].getValueString()
                        transcribedText.append([content.getName(), content.getParentPath(), outText.splitlines()])
                    else:
                        progressBar.updateStatusLabel("Transcribing file " + content.getName() + ". Be patient, this may take a while.")
                        self.log(Level.INFO,"Transcribing file " + content.getName())
                        
                        tmpPath = copyToTempFile(content)
                        
                        audioFilePath = convertAudioTo16kHzWav(content, tmpPath, self)

                        language = self.configPanel.combo.getSelectedItem()
                        
                        outText = transcribeFile(content, audioFilePath, language, True, self, SpeechToTextReportModule.moduleName)                    
                        
                        tagsManager.addContentTag(content, tagTranscribed)

                        # Fire an event to notify the UI and others that there is a new artifact
                        # This will update the Results -> Extracted Content -> Extrected Text GUI item
                        IngestServices.getInstance().fireModuleDataEvent(
                            ModuleDataEvent(SpeechToTextReportModule.moduleName,
                            BlackboardArtifact.ARTIFACT_TYPE.TSK_EXTRACTED_TEXT))

                        transcribedText.append([content.getName(), content.getParentPath(), outText.splitlines()])

                except Exception as e:
                    self.log(Level.SEVERE, "Error transcribing file: " + content.getName() +
                                "\nError: " + e.__repr__() )
                    
                progressBar.increment()

            if self.configPanel.radioButtonHTML.isSelected():
                mytemplate = Template(htmlTemplate)
                with open(fileName, 'w') as reportFile:
                    reportFile.write(str(mytemplate.render(transcriptions=transcribedText)))
                reportTitle = "Extracted text html"
            else:
                processedTranscribedText = map(lambda x: [x[0],x[1]," ".join(x[2]).replace("\n","")], transcribedText)
                processedTranscribedText = [["filename", "directory", "transcribed text"]] + processedTranscribedText
                self.log(Level.INFO, str(processedTranscribedText))
                with open(fileName, mode='wb') as reportFile:
                    csv_writer = csv.writer(reportFile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerows(processedTranscribedText)
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

        

 