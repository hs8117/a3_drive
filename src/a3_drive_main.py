#!/usr/bin/env python
# -*- coding: utf-8 -*-

####################################################################
# 프로그램명 : hough_drive.py
# 작 성 자 : 자이트론
# 생 성 일 : 2020년 08월 12일
# 수 정 일 : 2021년 03월 16일
# 검 수 인 : 조 이현
# 본 프로그램은 상업 라이센스에 의해 제공되므로 무단 배포 및 상업적 이용을 금합니다.
####################################################################

import rospy, rospkg
import numpy as np
import cv2, random, math
from cv_bridge import CvBridge
from xycar_msgs.msg import xycar_motor
from sensor_msgs.msg import Image
#from tkinter import *
from pid import PID
import sys
import os
import signal
import time

all_lines = []
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
fps = 30
frame_size = (640, 480)
out_bin = cv2.VideoWriter('/home/nvidia/xycar_ws/src/a3_drive/src/a3_bin_main.mp4', fourcc, fps, frame_size)
out_edge = cv2.VideoWriter('/home/nvidia/xycar_ws/src/a3_drive/src/a3_edge_main.mp4', fourcc, fps, frame_size)
out_track = cv2.VideoWriter('/home/nvidia/xycar_ws/src/a3_drive/src/a3_track_main.mp4', fourcc, fps, frame_size)

l_ = 1
r_ = 1

#speed = 45

# def change_dp(pos):
#     global pid
#     pid.Kp = pos
# def change_di(pos):
#     pid.Ki = pos
# def change_dd(pos):
#     pid.K
speed_tmp = 45


# def onchange( pos):
#     global speed
#     global speed_tmp
#     speed = pos
#     speed_tmp = speed


# cv2.namedWindow("TrackBar Test")
# cv2.createTrackbar("speed","TrackBar Test", 0, 45, onchange)


pid = PID(0.35, 0.0005, 0.05)


def signal_handler(sig, frame):
    os.system('killall -9 python rosout')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

image = np.empty(shape=[0])
bridge = CvBridge()
pub = None
Width = 640
Height = 480
Offset = 360
Gap = 40

def img_callback(data):
    global image
    image = bridge.imgmsg_to_cv2(data, "bgr8")

# publish xycar_motor msg
def drive(Angle, Speed):
    global pub

    if(Speed == 50):
        if (Angle < -10):
            Angle=-10
        elif(Angle > 10):
            Angle=10

    msg = xycar_motor()
    msg.angle = Angle
    msg.speed = Speed

    pub.publish(msg)

# draw lines
def draw_lines(img, lines):
    global Offset
    for line in lines:
        x1, y1, x2, y2 = line[0]
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        img = cv2.line(img, (x1, y1+Offset), (x2, y2+Offset), color, 2)
    return img

# draw rectangle
def draw_rectangle(img, lpos, rpos, offset=0):
    center = (lpos + rpos) / 2

    cv2.rectangle(img, (lpos - 5, 15 + offset),
                       (lpos + 5, 25 + offset),
                       (0, 255, 0), 2)
    cv2.rectangle(img, (rpos - 5, 15 + offset),
                       (rpos + 5, 25 + offset),
                       (0, 255, 0), 2)
    cv2.rectangle(img, (center-5, 15 + offset),
                       (center+5, 25 + offset),
                       (0, 255, 0), 2)
    cv2.rectangle(img, (315, 15 + offset),
                       (325, 25 + offset),
                       (0, 0, 255), 2)
    return img

# left lines, right lines
def divide_left_right(lines): #왼, 오 선분 나누는 함수
    global Width

    low_slope_threshold = 0
    high_slope_threshold = 10

    # calculate slope & filtering with threshold
    slopes = []
    new_lines = []

    for line in lines:
        x1, y1, x2, y2 = line[0]

        if x2 - x1 == 0: # 수직선일 경우 기울기 0
            slope = 0
        else:
            slope = float(y2-y1) / float(x2-x1)

        if abs(slope) > low_slope_threshold and abs(slope) < high_slope_threshold:
            slopes.append(slope)
            new_lines.append(line[0])

    # divide lines left to right
    left_lines = []
    right_lines = []

    for j in range(len(slopes)):
        Line = new_lines[j]
        slope = slopes[j]

        x1, y1, x2, y2 = Line


        if (slope < 0) and (x2 < Width/2 - 45):
            left_lines.append([Line.tolist()])
        elif (slope > 0) and (x1 > Width/2 + 45):
            right_lines.append([Line. tolist()])

    return left_lines, right_lines

# get average m, b of lines
def get_line_params(lines):

    # sum of x, y, m
    x_sum = 0.0
    y_sum = 0.0
    m_sum = 0.0

    size = len(lines)
    if size == 0:
        return 0, 0

    for line in lines:
        x1, y1, x2, y2 = line[0]
        x_sum += x1 + x2
        y_sum += y1 + y2
        m_sum += float(y2 - y1) / float(x2 - x1)

    x_avg = x_sum / (size * 2)
    y_avg = y_sum / (size * 2)
    m = m_sum / size
    b = y_avg - m * x_avg
    return m, b

# get lpos, rpos
def get_line_pos(img, lines, left=False, right=False):
    global Width, Height
    global Offset, Gap
    global l_,r_


    m, b = get_line_params(lines)
    if m == 0 and b == 0:
        if left:
            pos = 0
            l_ = 0
        if right:
            pos = Width
            r_ = 0
    else:
        if left:
            l_ = 1
        if right:
            r_ = 1
        y = Gap / 2
        pos = (y - b) / m

        b += Offset
        x1 = (Height - b) / float(m)
        x2 = ((Height/2) - b) / float(m)

        cv2.line(img, (int(x1), Height), (int(x2), (Height/2)), (255, 0,0), 3)

    return img, int(pos)

# show image and return lpos, rpos
def process_image(frame):
    global Width
    global Offset, Gap
    global l_,r_
    global out_track, out_edge, out_bin
    global all_lines
    # gray
    gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)

    # blur
    kernel_size = 5
    blur_gray = cv2.GaussianBlur(gray,(kernel_size, kernel_size), 0)

    _,binary_gray=cv2.threshold(blur_gray,110, 255, cv2.THRESH_BINARY)

    # canny edge
    low_threshold = 170
    high_threshold = 200
    edge_img = cv2.Canny(np.uint8(binary_gray), low_threshold, high_threshold)


    # HoughLinesP
    roi = edge_img[Offset : Offset+Gap, 0 : Width]
    all_lines = cv2.HoughLinesP(roi,1,math.pi/180,20,30,5)

    # divide left, right lines
    if all_lines is None:
        r_ = 0
        l_ = 0
        return 0, 640
    left_lines, right_lines = divide_left_right(all_lines)

    # get center of lines
    frame, lpos = get_line_pos(frame, left_lines, left=True)
    frame, rpos = get_line_pos(frame, right_lines, right=True)

    # draw lines
    frame = draw_lines(frame, left_lines)
    frame = draw_lines(frame, right_lines)
    frame = cv2.line(frame, (230, 235), (410, 235), (255,255,255), 2)

    # draw rectangle
    frame = draw_rectangle(frame, lpos, rpos, offset=Offset)
    #roi2 = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
    #roi2 = draw_rectangle(roi2, lpos, rpos)

    # show image
    cv2.imshow("binary_gray", binary_gray)
    binary_gray = cv2.cvtColor(binary_gray, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(binary_gray, (0, Offset), (640, Offset+ Gap), (0, 255, 255), 2)
    out_bin.write(binary_gray)

    cv2.imshow("edge_img",edge_img)
    edge_img = cv2.cvtColor(edge_img, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(edge_img, (0, Offset), (640, Offset+ Gap), (0, 255, 255), 2)
    out_edge.write(edge_img)

    cv2.imshow('calibration', frame)
    cv2.rectangle(frame, (0, Offset), (640, Offset+ Gap), (0, 255, 255), 2)
    out_track.write(frame)

    return lpos, rpos

def start():
    angle = 0
    global pub
    global image
    global cap
    global Width, Height
    global m_
    global l_,r_
    global pid
    global all_lines
    #global Offset
    kg = 0
    count_ = 0
    count = 0
    _count = 17
    global speed, speed_tmp
    speed = 20
    speed1 = 20
    speed2 = 7
    t = time.time()
    # speed = 0
    # speed1 = 0
    # speed2 = 0
    rospy.init_node('auto_drive')
    pub = rospy.Publisher('xycar_motor', xycar_motor, queue_size=1)

    image_sub = rospy.Subscriber("/usb_cam/image_raw", Image, img_callback)
    print "---------- Xycar A2 v1.0 ---------"
    rospy.sleep(1)

    while True:
        # trackbar1 = cv2.getTrackbarPos('speed', 'TrackBar Test')
        while not image.size == (640*480*3):
            continue


        lpos, rpos = process_image(image)


        #cv2.rectangle(image, (0, Offset), (640, Offset+Gap), (0, 255, 255))
        #cv2.line(image, (320-90, Offset), (320-90, Offset+Gap), (0, 255, 255))
        #cv2.line(image, (320+90, Offset), (320+90, Offset+Gap), (0, 255, 255))

        if kg == 1:
            Offset = 440
            count +=1
            speed = speed2
            center = (lpos + rpos) / 2
            #angle = -(Width/2 - center)
            error = (center - Width/2)
            if angle > 0:
                angle = 60
            elif angle < 0:
                angle = -60

            drive(angle,speed)
            if count > _count:
                kg = 0
                count = 0
                speed = speed1
            if l_ == 1 and r_ == 1:
                kg = 0
                speed = speed1

        else:
            if l_ == 0 and r_ == 0:
                center = (lpos + rpos) / 2
                #angle = -(Width/2 - center)
                error = (center - Width/2)
                drive(angle,speed)
                kg = 1

            else:
                Offset = 365
                # if count_ < 7:
                #     speed = 30
                # else:
                #     speed = speed1
                if count_ < 8:
                    speed = 50
                else:
                    speed = speed1
                center = (lpos + rpos) / 2
                #angle = -(Width/2 - center)
                error = (center - Width/2)


                angle = pid.pid_control(error)
                # if abs(angle) >30:
                #     speed = 10
                drive(angle,speed)

        count_= time.time()-t
        ### angle, kg, speed
        kg_text = "KG: " + str(kg)
        cv2.putText(image, kg_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255))

        angle_text = "Angle: " + str(angle)
        cv2.putText(image, angle_text, (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255))

        speed_text = "speed: " + str(speed)
        cv2.putText(image, speed_text, (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255)) #lines

        count_text = "count: " + str(count_)
        cv2.putText(image, count_text, (20, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255)) #lines

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    out_bin.release()
    out_edge.release()
    out_track.release()
    cv2.destroyAllWindows()
    sys.exit(0)
    #rospy.spin()

if __name__ == '__main__':
    start()
