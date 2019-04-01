# -*- coding: utf-8 -*-
"""
Created on Fri Dec  7 16:12:11 2018

@author: abhinav.jhanwar
"""

# face recognition modules
import face_recognition
import cv2
# mathematical tools
import numpy as np
# time modules
from time import gmtime, strftime, time
# models saving modules
import pickle
# image/video processing modules
from imutils.video import FPS
# json file handling module
import json

# read configuration file
with open('config.json', 'r') as outfile:  
    config = json.load(outfile)
base_dir = config['base_dir']
model_cfg = config['model_cfg']
model_weights = config['model_weights']

# define deep neural network parameters
net = cv2.dnn.readNetFromDarknet(model_cfg, model_weights)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)


##########################################################################
############################ Live video detection ########################
##########################################################################
def start_detection(camid=0):
    # load classifier
    pickle_in = open(base_dir+"svm_clf.pickle","rb")
    classifier = pickle.load(pickle_in)
    
    # setup camera to capture video
    video_capture = cv2.VideoCapture(camid)
    
    # start frames capturing timer
    fps = FPS().start()
    
    # start indefinite loop for video capturing
    while True:
        
        # fetch camera frame
        ret, frame = video_capture.read()
        
        # validate if image is captured, else stop video capturing
        if ret!=True:
            print("\nCamera not detected")
            video_capture.release()
            cv2.destroyAllWindows()
            return
        
        # load model parameters
        blob = cv2.dnn.blobFromImage(frame, 1 / 255, (416, 416),
                     [0, 0, 0], 1, crop=False)
        net.setInput(blob)
        
        # fetch model predictions
        layers_names = net.getLayerNames()
        outs = net.forward([layers_names[i[0] - 1] for i in net.getUnconnectedOutLayers()])
        
        # fetch captured image dimensions
        (frame_height, frame_width) = frame.shape[:2]
        
        # declare confidences, bounding boxes and face location bounding boxes list
        confidences = []
        boxes = []
        face_locations = []
        
        # looping through grid cells
        for out in outs:
            # looping through detectors
            for detection in out:
                # fetch classes probability
                scores = detection[5:]
                # fetch class with maximum probability
                class_id = np.argmax(scores)
                # fetch maximum probability
                confidence = scores[class_id]
                # filter prediction based on threshold value
                if confidence > conf_threshold:
                    # fetch validated bounding boxes
                    center_x = int(detection[0] * frame_width)
                    center_y = int(detection[1] * frame_height)
                    width = int(detection[2] * frame_width)
                    height = int(detection[3] * frame_height)
                    left = int(center_x - width / 2)
                    top = int(center_y - height / 2)
                    # add confidences and bounding boxes in list
                    confidences.append(float(confidence))
                    boxes.append([left, top, width, height])
        
        # perform non maximum suppression to remove overlapping images based on nms_threshold value           
        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold,
                                   nms_threshold)
        
        # fetch legitimate face bounding boxes
        for i in indices:
            i = i[0]
            box = boxes[i]
            left = box[0]
            top = box[1]
            width = box[2]
            height = box[3]
            face_locations.append(np.array([top, left+width, top+height, left
                         ]))
        
        # encode faces to be fed to classifier for prediction
        face_encodings = face_recognition.face_encodings(frame, face_locations, num_jitters=1)
        
        count=0
        # loop through face encodings and face boundary boxes
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            face_encoding = [face_encoding]
            # fetch probability distribution of predicted classes
            probabilities = classifier.predict_proba(face_encoding)[0]
            
            # fetch maximum probability value
            confidence = max(probabilities)
            
            # set name as unknown if confidence is lower than threshold value
            name = "Unknown"
            if confidence>conf_threshold:
                # fetch class with maximum probability
                name = classifier.classes_[np.argmax(probabilities)]
            
            # Draw a box around the face
            cv2.rectangle(frame, (left, top), (right, bottom), (255, 0, 0), 2)
    
            # Draw a label with a name below the face
            cv2.rectangle(frame, (left, bottom), (right, bottom+20), (255, 0, 0), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom+15), font, 0.5, (255, 255, 255), 1)
            
            if name!='Unknown':
                # put label for confidence
                cv2.rectangle(frame, (left, top-20), (right, top), (255, 0, 0), cv2.FILLED)
                cv2.putText(frame, str(round(confidence*100,2))+'%', (left + 6, top-3), font, 0.5, (255, 255, 255), 1)
                
            count+=1

        # Display the resulting image
        cv2.imshow('Face Recognition', frame)

        # Hit 'q' on the keyboard to quit!
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        
        # update the FPS counter
        fps.update()
     
    # stop the timer and display FPS information
    fps.stop()
    print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
    print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))
     
    # Release handle to the webcam
    video_capture.release()
    cv2.destroyAllWindows()


# detection
nms_threshold = 0.3
conf_threshold = 0.4
start_detection(0)
