# -*- coding: utf-8 -*-
"""
Created on Wed Apr 17 14:28:39 2019

@author: abhinav.jhanwar
"""

''' checking face using opencv if detected then yolo with margin, 
    histogram equalization and 
    then encoding 
    improved speed with batch processing in dlib
    '''

# face recognition modules
import face_recognition_models
import cv2
# classifier modules
from sklearn.svm import SVC
# model evaluation modules
from sklearn.model_selection import GridSearchCV
# mathematical tools
import numpy as np
from tqdm import tqdm
# directory modules
import os
import glob
# models saving modules
import _pickle as pickle
# json file handling module
import json
from sklearn import neighbors
import dlib
from PIL import ImageFile

###########################################################################
############################ training module ##############################
###########################################################################
class faceTraining:
    
    def __init__(self, config):
        
        self.base_dir = config['base_dir']
        model_cfg = config['model_cfg']
        model_weights = config['model_weights']
        self.user_images = config['ip_user_images']
        self.nms_threshold = config['nms_threshold']
        self.yolo_conf_threshold = config['yolo_conf_threshold']
        self.margin = config['margin_percent']
        
        self.net = cv2.dnn.readNetFromDarknet(model_cfg, model_weights)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        
        modelFile2 =  config['resnet_model']
        configFile2 =  config['resnet_cfg']
        self.net2 = cv2.dnn.readNetFromCaffe(configFile2, modelFile2)
        self.net2.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net2.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        
        self.names=[]
        for user in glob.glob(os.path.join(self.user_images,'*')):
            self.names.append(user.split('\\')[-1])
            
    def _css_to_rect(self, css):
        """
        Convert a tuple in (top, right, bottom, left) order to a dlib `rect` object
        :param css:  plain tuple representation of the rect in (top, right, bottom, left) order
        :return: a dlib `rect` object
        """
        return dlib.rectangle(css[3], css[0], css[1], css[2])

        
    def saveEncodings(self, verbose=True):
        
        # initialize face encoding parameters
        ImageFile.LOAD_TRUNCATED_IMAGES = True       
        predictor_68_point_model = face_recognition_models.pose_predictor_model_location()
        pose_predictor_68_point = dlib.shape_predictor(predictor_68_point_model)        
        predictor_5_point_model = face_recognition_models.pose_predictor_five_point_model_location()
        pose_predictor_5_point = dlib.shape_predictor(predictor_5_point_model)        
        face_recognition_model = face_recognition_models.face_recognition_model_location()
        face_encoder = dlib.face_recognition_model_v1(face_recognition_model)
        
        pose_predictor = pose_predictor_68_point
        
        # initialize a text file for saving images where faces are not found
        with open('waste_files.txt', 'w') as waste:
            waste.write("Images which are not suitable for training are-\n")
                    
            try:
                # load previously saved encodings
                pickle_in = open(self.base_dir+"known_face_encodings.pickle","rb")
                known_face_encodings = pickle.load(pickle_in)
                pickle_in.close()
                
                pickle_in = open(self.base_dir+"known_face_names.pickle","rb")
                known_face_names = pickle.load(pickle_in)
                pickle_in.close()
                # filter out faces which are already trained
                temp = []
                for name in self.names:
                    if name not in known_face_names:
                        temp.append(name)
                
                self.names = temp
                
            except:
                # declare encodings as empty
                known_face_encodings=[]
                known_face_names=[]
                #self.names = ['1231', '1232', '1234', '1238', '1242']#'1237', '1239','1235',  
            
            print("[INFO] Encoding... ", self.names)
            if self.names != []:
                # looping through names to be trained
                for name in tqdm(self.names):
                    # clear the lists for new user
                    face_images = []
                    faces_locations = []
                    face_names = []
                    
                    # load images of person to be trained
                    base = self.user_images
                    name = name.strip()
                    base = os.path.join(base, name)
                    # looping through images of person to be trained
                    for img_path in glob.glob(os.path.join(base, "*.jpg")):
                        # read image
                        image_data = cv2.imread(img_path)
                        
                        ###############
                        # check face using resnet
                        ###############
                        blob = cv2.dnn.blobFromImage(image_data, 1.0,
	                                        (300, 300), (104.0, 177.0, 123.0))
                        self.net2.setInput(blob)
                        detections = self.net2.forward()
                        (h, w) = image_data.shape[:2]
                        confidences = []
                        boxes = []
                        for i in range(0, detections.shape[2]):
                            confidence = detections[0, 0, i, 2]
                            if confidence > 0.98:
                                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                                box = box.astype("int")
                                # startX, startY, endX, endY
                                confidences.append(float(confidence))
                                boxes.append([box[0], box[1], box[2]-box[0], box[3]-box[1]])
            
                        if len(boxes)>0:
                            pass
                        else:
                           waste.write(img_path+"\n")
                           #print("[INFO] Image {} not suitable for training: Resnet filtered out".format(img_path))
                           continue
                       
                        ###############
                        # face detection using yolo
                        ###############
                        # load model parameters
                        blob = cv2.dnn.blobFromImage(image_data, 1 / 255, (416, 416),
                                         [0, 0, 0], 1, crop=False)
                        self.net.setInput(blob)
                        # fetch predictions from model/network
                        layers_names = self.net.getLayerNames()
                        outs = self.net.forward([layers_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()])
                        # fetch size of image
                        (frame_height, frame_width) = image_data.shape[:2]
                        # declare overall confidence list
                        confidences = []
                        # declare bounding boxes list
                        boxes = []
                        face_locations = []
                        # looping through model predictions/ predictions for each grid cell
                        for out in outs:
                            # looping through detectors outputs for grid cell
                            for detection in out:
                                # fetch classifier probabilities for different classes
                                scores = detection[5:]
                                # fetch maximum probabilty class
                                class_id = np.argmax(scores)
                                # define confidence as maximum probability
                                confidence = scores[class_id]
                                # filter predictions based on confidence threshold
                                if confidence > self.yolo_conf_threshold:
                                    # fetch bounding box dimensions
                                    center_x = int(detection[0] * frame_width)
                                    center_y = int(detection[1] * frame_height)
                                    width = int(detection[2] * frame_width)
                                    height = int(detection[3] * frame_height)
                                    left = int(center_x - width / 2)
                                    top = int(center_y - height / 2)
                                    # append confidence in confidences list
                                    confidences.append(float(confidence))
                                    # append bounding box in bounding boxes list
                                    boxes.append([left, top, width, height])
                        
                        # perform non maximum suppression of overlapping images
                        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.yolo_conf_threshold,
                                                   self.nms_threshold)
                        
                        # fetch faces bounding boxes
                        for i in indices:
                            i = i[0]
                            box = boxes[i]
                            left = box[0]
                            top = box[1]
                            width = box[2]
                            height = box[3]
                            face_locations.append(np.array([top, left+width+(width*self.margin//100), top+height, left-(width*self.margin//100)
                             ]))

                        if len(face_locations) != 1:
                            waste.write(img_path+"\n")
                            # If there are no people (or too many people) in a training image, skip the image.
                            if verbose:
                                pass
                                #print("[INFO] Image {} not suitable for training: {}".format(img_path, "Didn't find a face" if len(face_locations) < 1 else "Found more than one face"))
                        else:
                            for face_location in face_locations:
                                if min(face_location)<0:
                                    pass
                                    #print("[INFO] Image {} not suitable for training: Face is not in Boundary of Image".format(img_path))
                                else:
                                    ######################################################
                                    # histogram equalization
                                    frame1 = image_data[face_location[0]:face_location[2],face_location[3]:face_location[1],:]
                                    img_to_yuv = cv2.cvtColor(frame1, cv2.COLOR_BGR2YUV)
                                    img_to_yuv[:,:,0] = cv2.equalizeHist(img_to_yuv[:,:,0])
                                    frame1 = cv2.cvtColor(img_to_yuv, cv2.COLOR_YUV2BGR)
                        
                                    image_data[face_location[0]:face_location[2],face_location[3]:face_location[1],:] = frame1  
                                    ###################################################
                                    # Add face encoding for current image to the training set
                                    faces_locations.append(face_locations[0])
                                    face_images.append(image_data)
                                    face_names.append(name)
                
                    faces_locations = [self._css_to_rect(face_location) for face_location in faces_locations]

                    raw_landmarks = []
                    for face_image, face_location in zip(face_images, faces_locations):
                        faces = dlib.full_object_detections()
                        faces.append(pose_predictor(face_image, face_location))
                        raw_landmarks.append(faces)
                    
                    if len(faces_locations)<120:
                        print("[INFO]: %s skipped as total number of proper images are <120."%name)
                        continue
                    
                    # generate encoding for captured faces of user
                    encodings = list(np.array(face_encoder.compute_face_descriptor(batch_img=face_images, batch_faces=raw_landmarks, num_jitters=20))\
                                     .reshape((len(face_images), 128)))
                    
                    # append new data in old data
                    known_face_encodings += encodings
                    known_face_names += face_names
                    
                    # save the encodings after every iteration of distinct class
                    pickle_out = open(self.base_dir+"known_face_names.pickle","wb")
                    pickle.dump(known_face_names, pickle_out)
                    pickle_out.close()
                    pickle_out = open(self.base_dir+"known_face_encodings.pickle","wb")
                    pickle.dump(known_face_encodings, pickle_out)
                    pickle_out.close()
                    print("[INFO]: %s saved!"%name)
                
            else:
                print("Encoding Skipped!\n")
    
    def getEncodedNames(self):
        pickle_in = open(self.base_dir+"known_face_names.pickle","rb")
        known_face_names = pickle.load(pickle_in)
        pickle_in.close()
        return known_face_names
        
    def trainClassifier(self, optimize=False):
        # load dataset
        pickle_in = open(self.base_dir+"known_face_encodings.pickle","rb")
        known_face_encodings = pickle.load(pickle_in)
        pickle_in.close()
               
        pickle_in = open(self.base_dir+"known_face_names.pickle","rb")
        known_face_names = pickle.load(pickle_in)
        pickle_in.close()
        
        # Create and train the KNN classifier
        knn_clf = neighbors.KNeighborsClassifier(n_neighbors=1, weights='distance', n_jobs=-1)
        
        if optimize==True:
            # GridSearch for parameters optimization
            param_grid = {
                    'n_neighbors': list(range(1,51))
                    }
            grid = GridSearchCV(knn_clf, param_grid, verbose=3, n_jobs=10, cv=10)
            # fit model
            grid.fit(known_face_encodings, known_face_names)
            print("[INFO] Parameters selected for model:", grid.best_estimator_)
            print("[INFO] Score:", grid.best_score_)
            
        else:
            grid = knn_clf
            # fit model
            grid.fit(known_face_encodings, known_face_names)
                
        # save classifier
        pickle_out = open(self.base_dir+"knn_clf.pickle","wb")
        pickle.dump(grid, pickle_out)
        pickle_out.close()
        #knn_clf.fit(known_face_encodings, known_face_names)
        print("[INFO] %d Images trained and saved successfully"%len(known_face_names))
        

if __name__ == '__main__':
    
    # read configuration file
    with open('config_training.json', 'r') as outfile:  
        config = json.load(outfile)
      
    # define class object
    face = faceTraining(config)
    
    # encode names
    face.saveEncodings(verbose=True)
    
    # start training and save model
    face.trainClassifier(optimize=False)
            
    # get encoded names
    x = face.getEncodedNames()
    print('[INFO] Faces: ', sorted(set(face.getEncodedNames())))
    print('[INFO] Total number of people: ', len(set(face.getEncodedNames())))