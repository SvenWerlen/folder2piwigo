#!/usr/bin/env python
#! -*- coding: utf-8 -*-
"""
* Description
*
* @author Sven Werlen (sven.werlen@gmail.com)
* @copyright 2012 Sven Werlen
* @license GPL v3 (http://www.gnu.org/licenses/gpl.html)
* @package folder2piwigo
* @version 1.0 - 2013-01-08
"""

import os
import sys
import getopt
import unicodedata
import signal
import shutil
import re
import time
from ConfigParser import SafeConfigParser


class Folder2Piwigo(object):
   
   # settings
   sourceFolder = None
   targetFolder = None
   tempFolder   = None
   
   simulate = None
   delete = None
   
   imageResize = None
   imageQuality = None
   
   videoQuality = None
   
   
   # ===================================
   # Default constructor
   # ===================================
   def __init__(self,sourceFolder,targetFolder,tempFolder,simulate,delete,resize,imageQuality,videoQuality):
      
      self.sourceFolder = sourceFolder
      self.targetFolder = targetFolder
      self.tempFolder = tempFolder
      self.simulate = simulate
      self.delete = delete
      self.resize = resize
      self.imageQuality = imageQuality
      self.videoQuality = videoQuality
                 
      # check that input folder exists
      if self.sourceFolder is None:
         print "  [ERROR] No source folder specified!"
         sys.exit(1)
         
      if not os.path.exists(self.sourceFolder):
         print "  [ERROR] Input folder '" + self.sourceFolder + "' doesn't exist!"
         sys.exit(1)

      # check that target folder exists
      if self.targetFolder is None:
         print "  [ERROR] No target folder specified!"
         sys.exit(1)
      
      if not os.path.exists(self.targetFolder):
         print "  [ERROR] Target folder '" + self.targetFolder + "' doesn't exist!"
         sys.exit(1)

      # check that temp folder exists
      if self.tempFolder is None:
         print "  [ERROR] No temp folder specified!"
         sys.exit(1)
      
      if not os.path.exists(self.tempFolder):
         print "  [ERROR] Temp folder '" + self.tempFolder + "' doesn't exist!"
         sys.exit(1)
      
      
   
   # ===================================
   # Executes the process
   # ===================================
   def run(self):
      self.process(self.sourceFolder)
   
   # ===================================
   # Processes on folder and its subfolders (by recursion)
   # ===================================
   def process(self, curFolder):
      
      # CTRL+C signal
      signal.signal(signal.SIGINT, quit_gracefully)
      
      # verbose
      print ""
      print "  Processing folder '" + curFolder + "'..."   
      
      # skip folder (and subfolders) if .nosync
      if os.path.exists(os.path.join(curFolder, ".nosync")):
         print "    Folder '" + curFolder + "' and all subfolders skipped."
         return

      # build output folder path
      outputDir = curFolder.replace(self.sourceFolder,"")
      outputDir = self.targetFolder + self.utilFixPath(outputDir)   
      
      # create output folder if not exist
      if not os.path.exists(outputDir):
         print "    Folder '" + outputDir + "' doesn't exist. Creating..."
         if not self.simulate:
            os.mkdir(outputDir)

      
      # loop over all elements
      processed = set([])
      elDone = 0
      elSkipped = 0
      elDeleted = 0
      for el in os.listdir(curFolder):
         try:
            curPath = os.path.join(curFolder,el)
            
            # ignore system files
            if el.startswith("."):
               continue
            
            # file => process image
            if os.path.isfile(curPath):
               # add element into set (necessary for --delete option)
               processed.add(self.utilFixPath(el))
               
               # retrieve relative paths
               elementPath  = curPath
               outputFile = os.path.join(outputDir, el)
               outputFile = self.utilFixPath(outputFile)
               
               # check if file exists
               if not os.path.exists(outputFile):
               
                  # file is an image?
                  filename, fileext = os.path.splitext(outputFile)
                  if fileext.lower() in [".jpg",".jpeg",".gif",".png"]:
                     nothing = True
                     print "    Processing image '" + outputFile + "'..."
                                       
                     # create images
                     if not self.simulate:
                        self.createImage(elementPath, outputFile)
                     
                     # increase counter
                     elDone += 1
                  
                  # file is a video?
                  elif fileext.lower() in [".ogv",".ogg",".mp4"]:
                     print "    Processing video '" + outputFile + "'..."
                     
                     # create videos
                     if not self.simulate:
                        self.createVideo(elementPath, self.utilFixPath(el), outputDir, outputFile)
                     
                     # increase counter
                     elDone += 1
                  
               else:
                  elSkipped += 1
            
            # folder => process sub-folder
            elif os.path.isdir(curPath):
               self.process(curPath)
            
                  
         except KeyboardInterrupt:
            quit_gracefully()


      # delete non-processed elements
      if self.delete  and os.path.exists(outputDir) and os.path.isdir(outputDir):
         for el in os.listdir(outputDir):
            try:
               curPath = os.path.join(outputDir,el)
               
               # ignore system files
               if el.startswith("."):
                  continue
               
               # file => check image
               if os.path.isfile(curPath):
                  # retrieve relative paths
                  elementPath  = curPath
                  
                  # check file extension
                  filename, fileext = os.path.splitext(elementPath)
                  if not fileext.lower() in [".jpg",".jpeg",".gif",".png",".mp4",".ogg"]:
                     continue
                  
                  # check if file was processed
                  if not el in processed:
                     print "    Element '" + elementPath + "' has no match in source folder. Deleting..."
                     
                     # delete file
                     if not self.simulate:
                        delCommand = 'rm -f #INTERACTIVE "#SRCFILE"'
                        delCommand = delCommand.replace('#INTERACTIVE','-i') if self.delete == "Prompt" else delCommand.replace('#INTERACTIVE','')
                        delCommand = delCommand.replace('#SRCFILE',elementPath)
                        os.system(delCommand)

                     # increase counter
                     elDeleted += 1            
                     
            except KeyboardInterrupt:
               quit_gracefully()
         
      # verbose
      print "    (" + str(elDone) + " elements processed / " + str(elSkipped) + " elements skipped / " + str(elDeleted) + " elements deleted)"


   # ===================================
   # Generates a new image from the source
   #  - Automatically rotates based on EXIF information
   #  - Applies desired quality
   #  - Resizes image (if desired)
   # ===================================
   def createImage(self, srcFile, destFile):

      # temporary file
      tempfile = os.path.join(self.tempFolder, 'temp.jpg')

      # command
      imCommand = 'convert -auto-orient -quality #QUALITY #RESIZEOPT "#SRCFILE" "#DESTFILE"'
      
      # replace place holders by values
      imCommand = imCommand.replace('#QUALITY',str(self.imageQuality)) if self.imageQuality is not None else imCommand.replace('#QUALITY','95')
      imCommand = imCommand.replace('#RESIZEOPT',"-resize " + self.imageResize) if self.imageResize is not None else imCommand.replace('#RESIZEOPT','')
      imCommand = imCommand.replace('#SRCFILE',srcFile)
      imCommand = imCommand.replace('#DESTFILE',tempfile)
      
      # execute command
      os.system(imCommand)
      
      # copy to destination
      shutil.copy(tempfile, destFile)
   
   
   # ===================================
   # Generates a new video from the source
   #  - Automatically converts to Ogg Vorbis format
   #  - Applies desired quality
   #  - Optimizes compression (reduces size)
   #  - Extracts an image from the video as representative
   #  - Adds EXIF date to representative
   # ===================================
   def createVideo(self, srcFile, filename, destFolder, destFile):
         
      # extract filename
      filename, fileext = os.path.splitext(filename)
      
      # folders
      thumbFolder = os.path.join(destFolder,'pwg_representative')
      tempThumb = os.path.join(self.tempFolder, 'temp.jpg')
      tempVideo = os.path.join(self.tempFolder, 'vid.ogg')
      
      # create output folders if not exist
      if not os.path.exists(thumbFolder):
         os.mkdir(thumbFolder)
      
      # commands
      thumbCommand = 'avconv -y -i "#SRCFILE" -vframes 1 -ss 00:00:01 -an -vcodec mjpeg -f rawvideo -v quiet "#DESTFILE"';
      vidCommand   = 'ffmpeg2theora --framerate 24 --videoquality #QUALITY --optimize -o "#DESTFILE" "#SRCFILE" ';
      exifCommand  = 'exiftool -EXIF:DateTimeOriginal="#DATE" "#SRCFILE"';
      
      # generate thumbnail
      thumbCommand = thumbCommand.replace('#SRCFILE',srcFile)
      thumbCommand = thumbCommand.replace('#DESTFILE',tempThumb)
      os.system(thumbCommand)
      
      # re-encode video (less quality and optimized compression)
      vidCommand = vidCommand.replace('#SRCFILE',srcFile)
      vidCommand = vidCommand.replace('#DESTFILE',tempVideo)
      vidCommand = vidCommand.replace('#QUALITY',str(self.videoQuality)) if self.videoQuality is not None else vidCommand.replace('#QUALITY','5')
      os.system(vidCommand)
      
      # extract creation date 
      createDate = self.utilExtractTime(filename)
      
      # inject exif metadata
      exifCommand = exifCommand.replace('#SRCFILE',tempThumb)
      exifCommand = exifCommand.replace('#DATE',createDate)
      os.system(exifCommand)

      # copy thumbnails
      shutil.copy(tempThumb, os.path.join(thumbFolder,filename + '.jpg'))

      # copy video to destination
      shutil.copy(tempVideo, destFile)
      
      

   # ===================================
   # Utility function which tries to extract the date time from the video
   #    1) From filename (format _YYYYMMDD_HHMMSS)
   # ===================================
   def utilExtractTime(self, filename):
      search = re.search('_([0-9]{8}_[0-9]{6})',filename)
      date = "";
      if search == None:
         return ""
      else:
         date = search.group(1)
         date = time.strptime(date,'%Y%m%d_%H%M%S')
         return time.strftime("%Y:%m:%d %H:%M:%S", date)
   

   # ===================================
   # Utility function that applies some rules on paths
   # according to Piwigo restrictions
   # ===================================
   def utilFixPath(self, path):
      path = path.lower()
      path = path.replace(" ", "_")
      path = path.replace("(", "")
      path = path.replace(")", "")
      path = path.replace(",", "")
      path = path.replace("&", "")
      path = path.replace("'", "")
      path = path.replace(".ogv", ".ogg")
      
      nkfd_form = unicodedata.normalize('NFKD', unicode(path,'utf8'))
      path = u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
      return path.encode("ascii", "ignore")



# ===============================================================================================
# ===============================================================================================
# ===============================================================================================
# ===============================================================================================
# ===============================================================================================



# ===================================
# Prints the script usage and exists
# ===================================
def usage():
   print 'folder2piwigo4.py -i <inputfolder> [-o <outputfolder>] [--delete] [--simulate]'
   sys.exit(2)

# ===================================
# To handle signals
# ===================================
def quit_gracefully(*args):
   print 'Quitting...'
   sys.exit(0)

# ===================================
# Main
# ===================================
def main(argv):
   config = None
   sourceFolder = None
   targetFolder = None
   tempFolder = None
   simulate = None
   delete = None
   imgResize = None
   imgQuality = None
   videoQuality = None
   
   # CTRL+C signal
   signal.signal(signal.SIGINT, quit_gracefully)
    
   # read settings from command line options
   try:
      opts, args = getopt.getopt(argv,"hdsi:o:t:c:",["config=","input=","output=","temp=","delete", "simulate"])
      
   except getopt.GetoptError:
      usage()
   for opt, arg in opts:
      if opt in ("-h", "--help"):
         usage()
      elif opt in ("-c", "--config"):
         config = arg
      elif opt in ("-i", "--input"):
         sourceFolder = arg
      elif opt in ("-o", "--output"):
         targetFolder = arg
      elif opt in ("-t", "--temp"):
         tempFolder = arg
      elif opt in ("-d", "--delete"):
         delete = True
      elif opt in ("-s", "--simulate"):
         simulate = True

   # read config file and merge settings
   # (settings from command line have priority on settings from config file)
   defaultConfigPath = os.path.join(os.getenv("HOME"),".folder2piwigo")
   config = defaultConfigPath if os.path.exists(defaultConfigPath) and os.path.isfile(defaultConfigPath) else config
   
   if config is not None:
      # check that file exists
      if not os.path.exists(config):
         print "[ERROR] Configuration file '" + config + "' doesn't exist!"
         sys.exit(1)
      parser = SafeConfigParser()
      parser.read(config)
      
      # load settings if not already set
      if parser.has_section('Folders'):
         sourceFolder = parser.get('Folders', 'SourceFolder') if sourceFolder is None and parser.has_option('Folders','SourceFolder') else sourceFolder
         targetFolder = parser.get('Folders', 'TargetFolder') if targetFolder is None and parser.has_option('Folders','TargetFolder') else targetFolder
         tempFolder = parser.get('Folders', 'TempFolder') if tempFolder is None and parser.has_option('Folders','TempFolder') else tempFolder
      if parser.has_section('Settings'):
         simulate = parser.getboolean('Settings', 'Simulate') if simulate is None and parser.has_option('Settings','Simulate') else simulate
         delete = parser.get('Settings', 'Delete') if delete is None and parser.has_option('Settings','Delete') else delete
         delete = False if delete == "Off" else delete
      if parser.has_section('Images'):
         imgResize = parser.get('Images', 'Resize') if imgResize is None and parser.has_option('Images','Resize') else imgResize
         imgQuality = parser.getint('Images', 'Quality') if imgQuality is None and parser.has_option('Images','Quality') else imgQuality
      if parser.has_section('Videos'):
         videoQuality = parser.getint('Videos', 'Quality') if videoQuality is None and parser.has_option('Videos','Quality') else videoQuality

   # apply default settings
   simulate = False if simulate is None else simulate
   delete = False if delete is None else delete
   imgQuality = 95 if imgQuality is None else imgQuality
   videoQuality = 5 if videoQuality is None else videoQuality
    
   # print settings (debug)
   print '#################################'
   print 'Source folder:  ', sourceFolder
   print 'Target folder:  ', targetFolder
   print 'Temp   folder:  ', tempFolder
   print 'Simulation Mode:', simulate
   print 'Deletion Mode:  ', delete
   print 'Image Resize:   ', imgResize
   print 'Image Quality:  ', imgQuality
   print 'Video Quality:  ', videoQuality
   print '#################################'

   if delete and not simulate:
      print "Deletion has been enabled! All files in output folders that don't exist in corresponding input folders will be DELETED!"
      print "Please confirm by pressing ENTER or abort with CTRL+C"
      raw_input("")
         
   p = Folder2Piwigo(sourceFolder,targetFolder,tempFolder,simulate,delete,imgResize,imgQuality,videoQuality)
   p.run()


# ===================================
# Main exec
# ===================================
if __name__ == "__main__":
   main(sys.argv[1:])

