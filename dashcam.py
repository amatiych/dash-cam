from time import sleep
from PIL import Image
import math
from picamera import PiCamera, color
from datetime import datetime
import os
import threading
from subprocess import call
from core import setup_logging, capture_ex, Location, free_space
import json
import re



def sorted_ls(path):
        mtime = lambda f: os.stat(os.path.join(path, f)).st_mtime
        return list(sorted(os.listdir(path), key=mtime))

def convert(filename):
        mp4name = filename.replace("h264","mp4")
        call(["MP4Box","-add", filename, mp4name])
        return mp4name

class CleanerThread(threading.Thread):

        def __init__(self, folder, tokeep,log, ext = 'h264'):
                self.folder = folder
                self.log = log
                self.thumb_folder = os.path.join(folder,"thumbs/")
                self.tokeep = tokeep
                self.ext = ext
                super(CleanerThread, self).__init__()

        def delfile(self, folder,name):
                fullpath = os.path.join(folder,name)
                if os.path.exists(fullpath):
                        log.info("deleting % s : " % fullpath)
                        os.remove(fullpath)
        @capture_ex
        def clean(self):
                files = sorted([f for f in os.listdir(self.folder) if 'lock' not in f and self.ext in f])
                todel = max(0,len(files) - self.tokeep)
                log.info("Need to delete %s files out of %s in order to keep %s" %(todel,len(files),self.tokeep))

                for i in range(todel):
                        file = files[i]
                        th_file = re.sub("h264","jpg",file)
                        log.info("deleting %s and %s  " % (file,th_file))
                        self.delfile(self.folder,file)
                        self.delfile(self.thumb_folder,th_file)
        
        def run(self):
                while True:
                        self.clean()
                        sleep(60)

def get_changed_pixels(buffer1, buffer2,threshold):
        changedPixels = 0
        X,Y = (640,480) #buffer1.size
        total_pixels = X*Y 
        for x in range(X):
               for y in range( Y):
                        # Just check green channel as it's the highest quality channel
                        pixdiff = abs(buffer1[x,y][1] - buffer2[x,y][1])
                        if pixdiff > threshold:
                                 changedPixels += 1
        return changedPixels, 100.0 * changedPixels / total_pixels

class DashCamThread():

        def __init__(self,*,video_length, features, folder, loc):
                self.loc = loc
                self.prev_loc = Location()
                self.duration = video_length
                self.cam = PiCamera()
                self.cam.hflip = features["hflip"]
                self.cam.vflip = features["vflip"]
                self.cam.annotate_text_size = int(12)
                self.cam.annotate_background = color.Color('black')
                self.cam.annotate_foreground = color.Color(y=1.0, u=0,v=0)
                self.camera_name = features['name']
                self.folder = folder
                super(DashCamThread,self).__init__()

        def get_file_name(self):
                timestamp = lambda : datetime.now().strftime("%Y%m%d_%H%M%s")
                while True:
                        filename =  str.format("{0}_{1}.h264", self.camera_name, timestamp())
                        jpgname =  str.format("{0}_{1}.jpg", self.camera_name, timestamp())
                        yield os.path.join(self.folder, filename), os.path.join(self.folder,"thumbs", jpgname)
                        sleep(0.1)
                        
        @capture_ex        
        def run(self):
                try:

                        snapshot_filename = os.path.join(self.folder,"snapshot.jpg")
                        self.cam.capture(snapshot_filename,use_video_port=True)
                        prev_buf = Image.open(snapshot_filename).load()
                        lock = False
                        for filename,jpgname in self.get_file_name():
                                if filename:
                                        log.info("recording %s " % filename)
                                        self.cam.capture(jpgname,use_video_port=True)
                                        self.cam.start_recording(filename +'.lock',format='h264')
                                        start = datetime.now()
                                        while (datetime.now() - start).seconds < self.duration:
                                            if loc.lat != 0: 
                                                if prev_loc.lat != 0:
                                                    mph = speed(loc,prev_loc) 
                                                    gps_str = " (%.6f,%.6f),speed: %.0f" % (loc.lat,loc.lng,mph) 
                                                else:
                                                    gps_str = " (%.6f,%.6f)" % (loc.lat,loc.lng)
                                                self.cam.annotate_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + gps_str
                                                prev_loc.lat = loc.lat   
                                                prev_loc.lng = loc.lng   
                                            else:    
                                                self.cam.annotate_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                            self.cam.capture(snapshot_filename,use_video_port=True)
                                            buf = Image.open(snapshot_filename).load()
                                            chg,pct = get_changed_pixels(prev_buf, buf, 50)
                                            buf,prev_buf = prev_buf,buf
                                            log.info("changed %s pixels or %s pct" %(chg,pct))
                                            if pct > 1:
                                                    log.info("MOTION DETECTED")
                                                    lock = True

                                            self.cam.wait_recording(1)
	

                                        self.cam.stop_recording()
                                        if not lock:
                                                log.info("renaming file from %s to %s"  % (filename + '.lock', filename))
                                                os.rename(filename+'.lock', filename)
                                        lock = False
                except Exception as ex:
                        log.error(ex)
                                
                
def config():
        with open ("/home/pi/features.json") as f:
                features = json.load(f)
        return features
        
if __name__ == '__main__':
       
        folder = "/home/pi/Documents/videos"
        log = setup_logging(name="dashcan daemon",fileName="/home/pi/Documents/log/dashcam.log")
        log.info("starting dashcam  daemon")

        #initialize location objects. 
        loc = Location()
        prev_loc = Location()
        features = config()

        have_gps = features["gps"]
        if have_gps:
                from gps import distance,GPSThread, speed
                gps = GPSThread(loc)        
                gps.start()
    
        log.info(features)

        camthread = DashCamThread(video_length=60,features=features, folder=folder,loc=loc)
        cleaner = CleanerThread(folder, 60*24,log,"h264")
        
        log.info("Starting main threads")
 
        cleaner.start()
        camthread.run()
        
 
      
 
     

                
      

        
        

