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
import json
import requests
from ConfigParser import SafeConfigParser


# ===================================
# Piwigo client interface
# ===================================
class AbstractPiwigoClient(object):

   # target settings
   target = None

   def __init__(self,target):
      self.target = target

   def categoryExists(self, category):
      r = requests.get(self.target, "")
      pass

   def addCategory(self, category):
      pass

   def fileExists(self, category, filename):
      pass
   
   def addImage(self, file, category, filname):
      pass

   def addOther(self, file, representative, category, filname, ):
      pass
   
   def cleanCategory(self, category, fileList):
      pass



# ===================================
# ===================================
# Pwigio file-based implementation
# ===================================
# ===================================
class PiwigoFileClient(AbstractPiwigoClient):

   # Converts path according to Piwigo file restrictions
   def convertPath(self, path):
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


   def convertCategoryPath(self, path):
      category = self.convertPath(path)
      return os.path.join(self.target, category)

   def convertFilePath(self, cPath, fPath):
      category = self.convertCategoryPath(cPath)
      file = self.convertPath(fPath)
      return os.path.join(category,file)


   def categoryExists(self, category):
      return os.path.exists(self.convertCategoryPath(category))
      
   def addCategory(self, category):
      os.mkdir(self.convertCategoryPath(category))

   def fileExists(self, category, filename):
      return os.path.exists(self.convertFilePath(category, filename))
   
   def addImage(self, file, category, filename):
      shutil.copy(file, self.convertFilePath(category, filename))

   def addOther(self, file, representative, category, filename):
      # generate representative path and name
      rFolder = os.path.join(category,'pwg_representative')
      name, ext = os.path.splitext(filename)
      rFilename = name + ".jpg"
      
      # treat representative folder like a category
      if not self.categoryExists(rFolder):
         self.addCategory(rFolder)
      
      tRepresentative = self.convertFilePath(rFolder, rFilename)
      tFile = self.convertFilePath(category, filename)
      
      # copy files
      try:
         shutil.copy(representative, tRepresentative)
         shutil.copy(file, tFile)
      except IOError:
         # could happen with big files
         # check if file size is the same => if not, remove target file
         statinfo1 = os.stat(representative)
         statinfo2 = os.stat(tRepresentative)
         if not statinfo1.st_size == statinfo2.st_size:
            os.remove(tRepresentative)
         statinfo1 = os.stat(file)
         statinfo2 = os.stat(tFile)
         if not statinfo1.st_size == statinfo2.st_size:
            os.remove(tFile)
         
         

   def cleanCategory(self, category, fileList, prompt):
      # generate a new list (filename converted)
      newFileList = set([])
      for f in fileList:
         newFileList.add(self.convertPath(f))
         
      # delete
      deleted = 0
      for el in os.listdir(self.convertCategoryPath(category)):
         curPath = self.convertFilePath(category, el)
         
         # ignore system files
         if el.startswith("."):
            continue
         
         # check file extension
         name, ext = os.path.splitext(curPath)
         if not ext.lower() in [".jpg",".jpeg",".gif",".png",".mp4",".ogg"]:
            continue
            
         # check if file was processed
         if not el in newFileList:
            print "    Element '" + el + "' has no match in source folder. Deleting..."
            
            # delete file
            delCommand = 'rm -f #INTERACTIVE "#SRCFILE"'
            delCommand = delCommand.replace('#INTERACTIVE','-i') if prompt else delCommand.replace('#INTERACTIVE','')
            delCommand = delCommand.replace('#SRCFILE',self.convertFilePath(category, el))
            os.system(delCommand)

            # increase counter
            deleted += 1
     
      return deleted
                     



# ===================================
# ===================================
# Pwigio api-based implementation
# ===================================
# ===================================
class AbstractPiwigoClient(object):

   # target settings
   baseURL = None
   cookie = None
   
   # cache
   cacheCategoryId = None
   cacheCategory   = None
   cacheImages     = None


   def __init__(self,target):
      self.baseURL = target
      data = {'username': 'admin', 'password': 'test123456'}
      self.request('pwg.session.login', data)

   def __del__(self):
      self.request('pwg.session.logout', {})

   # ===================================
   # Piwigo request to web API
   # ===================================
   def request(self, method, content):
      params = {'method': method, 'format': 'json'}
      cookies = dict(pwg_id=self.cookie) if not self.cookie is None else None
      r = requests.post(self.baseURL + '/ws.php', params=params, data=content, cookies=cookies)
      result = r.json
      
      # debug
      print r.url
      
      # store cookie (1st time)
      if self.cookie is None:
         self.cookie = r.cookies['pwg_id']
      
      if result is None:
         # strange: logout doesn't return any result??
         if not method == 'pwg.session.logout':
            print "  [ERROR] Communication error (empty result)"
            sys.exit(1)
      elif result['stat'] == 'ok':
         return result['result']
      else:
         print "  [ERROR] Communication error [" + str(result['err']) + "]: " + result['message']
         sys.exit(1)
   
   # ===================================
   # Retrieves categoryId from path
   # ===================================
   def getCategoryId(self, category):
      # check cache
      if self.cacheCategory == category:
         return self.cacheCategoryId
      
      if category == "":
         return None
      
      # remove first '/'
      if category.startswith('/'):
         category = category[1:]
      
      categories = category.split('/')
      cur = 0
      found = False

      for cat in categories:
         result = self.request('pwg.categories.getList', {'cat_id': cur})
         for c in result['categories']:
            # current category found
            if c['name'].encode('utf-8') == cat:
               cur = c['id']
               found = True
         
         if not found:
            return None
         
      return cur if found else None
         
   
   # ===================================
   # Retrieves parentCategoryId from path
   # ===================================
   def getParentCategoryId(self, category):
      # remove last part
      parentCategory = category[:category.rfind('/')]
      return getCategoryId(parentCategory)
      

   def categoryExists(self, category):
      # check cache
      if self.cacheCategory == category:
         return True
      
      # root category always exists
      if category == "":
         return True
         
      catId = self.getCategoryId(category)
      if catId is None:
         return False
         
      # update cache
      self.cacheCategoryId = catId
      self.cacheCategory = category
      self.cacheImages = None
      return True
      

   def addCategory(self, category):
      index = category.rfind('/')
      parentCategory = "" if index < 0 else category[:category.rfind('/')]
      parentCategoryId = "" if index < 0 else self.getCategoryId(parentCategory)
      currentCategory = category if index < 0 else category[category.rfind('/')+1:]
      
      print "Parent = " + parentCategory
      print "Current = " + currentCategory
      
      # ignore root category
      if currentCategory == "":
         return
      
      params = {}
      if parentCategoryId is None:
         params = {'name': currentCategory}
      else:
         params = {'name': currentCategory,'parent': str(parentCategoryId)}
      
      # create new album
      self.request('pwg.categories.add', params)
      
      

   def fileExists(self, category, filename):
      
      categoryId = self.getCategoryId(category) if self.categoryExists(category) else None
      
      if categoryId is None:
         return False
      
      #result = self.request('pwg.categories.getImages', {'cat_id': categoryId, 'per_page': {10000}})
      #for i in result['images']
         
      return False
   
   def addImage(self, file, category, filname):
      donothing = True

   def addOther(self, file, representative, category, filname, ):
      donothing = True
   
   def cleanCategory(self, category, fileList):
      return 0





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
   
   client = None
   
   
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
      #self.client = PiwigoFileClient(targetFolder)
      self.client = AbstractPiwigoClient("http://piwi.chummix.org/ws.php")
      
                 
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
      category = curFolder.replace(self.sourceFolder,"")
      
      # create output folder if not exist
      if not self.client.categoryExists(category):
         print "    Category '" + category + "' doesn't exist. Creating..."
         if not self.simulate:
            self.client.addCategory(category)
      
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
               processed.add(el)
               
               # retrieve relative paths
               filePath  = curPath
               
               # check if file exists
               if not self.client.fileExists(category, el):
               
                  # file is an image?
                  filename, fileext = os.path.splitext(el)
                  if fileext.lower() in [".jpg",".jpeg",".gif",".png"]:
                     print "    Processing image '" + el + "'..."
                                       
                     # create images
                     if not self.simulate:
                        self.client.addImage(self.createImage(filePath), category, el)
                     
                     # increase counter
                     elDone += 1
                  
                  # file is a video?
                  elif fileext.lower() in [".ogv",".ogg",".mp4"]:
                     print "    Processing video '" + el + "'..."
                     
                     # create videos
                     if not self.simulate:
                        video, thumb = self.createVideo(filePath)
                        self.client.addOther(video, thumb, category, el)
                     
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
      if self.delete and os.path.exists(curFolder) and os.path.isdir(curFolder):
         if not self.simulate:
            elDeleted = self.client.cleanCategory(category, processed, self.delete == "Prompt")
         
      # verbose
      print "    (" + str(elDone) + " elements processed / " + str(elSkipped) + " elements skipped / " + str(elDeleted) + " elements deleted)"


   # ===================================
   # Generates a new image from the source
   #  - Automatically rotates based on EXIF information
   #  - Applies desired quality
   #  - Resizes image (if desired)
   # ===================================
   def createImage(self, srcFile):

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
      
      return tempfile
   
   
   # ===================================
   # Generates a new video from the source
   #  - Automatically converts to Ogg Vorbis format
   #  - Applies desired quality
   #  - Optimizes compression (reduces size)
   #  - Extracts an image from the video as representative
   #  - Adds EXIF date to representative
   # ===================================
   def createVideo(self, srcFile):
         
      # folders
      tempThumb = os.path.join(self.tempFolder, 'temp.jpg')
      tempVideo = os.path.join(self.tempFolder, 'vid.ogg')
      
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
      createDate = self.utilExtractTime(srcFile)
      
      # inject exif metadata
      exifCommand = exifCommand.replace('#SRCFILE',tempThumb)
      exifCommand = exifCommand.replace('#DATE',createDate)
      os.system(exifCommand)

      return tempVideo, tempThumb
      
      

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


# ===============================================================================================
# ===============================================================================================
# ===============================================================================================
# ===============================================================================================
# ===============================================================================================



# ===================================
# Prints the script usage and exists
# ===================================
def usage():
   print 'folder2piwigo.py -i <inputfolder> [-o <outputfolder>] [--delete] [--simulate]'
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

