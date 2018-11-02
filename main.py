#!/usr/bin/env python
# -*- coding: utf-8 -*-
import atexit
#import inspect
#from msilib.schema import File

from PyQt5.QtWidgets import (QApplication, QSplashScreen, QProgressBar, QLabel)

from controller import Controller
from parameters import AppParameters
from sceneRender import *
#from sceneData import *
import logging
import cProfile
import os
import platform
#import shutil


__author__ = 'Tibor Vavra'

DEBUG = False

class EventLoopRunner(QObject):
    finished = pyqtSignal()

    def __init__(self, app, base_path=""):
        super(EventLoopRunner, self).__init__()
        self.base_path = base_path
        self.app = app
        self.version = ""
        self.system_platform = platform.system()
        self.progressbar_on = 0


        with __builtins__.open(self.base_path + "data/v.txt", 'r') as version_file:
            self.version_full = version_file.read()
            self.version = AppParameters.strip_version_string(self.version_full)


        self.is_running = True
        self.css = []
        self.splash_pix = []
        self.splash = []
        self.progressBar = []
        self.version_label = []

        self.initializeGUI()

    def initializeGUI(self):

        self.css = QFile(self.base_path + 'data/my_stylesheet.qss')
        self.css.open(QIODevice.ReadOnly)


        if self.system_platform in ["Darwin"]:
            self.splash_pix = QPixmap(self.base_path + 'data/img/splashscreen_osx.png')    
            self.progressbar_on = 0
        else:
            self.splash_pix = QPixmap(self.base_path + 'data/img/splashscreen.png')
            self.progressbar_on = 1
        self.splash = QSplashScreen(self.splash_pix, Qt.SplashScreen | Qt.WindowStaysOnTopHint)

        if self.progressbar_on:
            self.progressBar = QProgressBar(self.splash)
            self.progressBar.setStyleSheet(str(self.css.readAll()))
            self.progressBar.setObjectName("splash_progressbar")
            self.progressBar.setFormat("")
            self.progressBar.setFixedWidth(209)
            self.progressBar.setFixedHeight(6)
            self.progressBar.move(245, 453)

        self.version_label = QLabel(self.version, self.splash)
        self.version_label.setObjectName("version_label")
        self.version_label.move(620, 647)
        self.version_label.setFixedWidth(100)

        self.splash.show()

        self.set_progress(0)

    def process_event_loop(self):
        while self.is_running == True:
            self.app.processEvents()

    def set_progress(self, value):
        if self.progressbar_on:
            self.progressBar.setValue(value)



def log_exception(excType, excValue, traceback):
    logging.error("Logging an uncaught exception",
                 exc_info=(excType, excValue, traceback))

    sys.__excepthook__(excType, excValue, traceback)



def main():
    QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads, True)
    if getattr(sys, 'frozen', False):
        # it is freeze app
        base_dir = sys._MEIPASS
    else:
        # we are running in a normal Python environment
        base_dir = os.path.dirname(os.path.abspath(__file__))

    system_platform = platform.system()
    if system_platform in ['Windows']:
        base_dir+='\\'
    else:
        base_dir+='/'

    sys.excepthook = log_exception
    app = QApplication(sys.argv)

    event_loop_runner = EventLoopRunner(app, base_dir)
    event_loop_runner_thread = QThread()
    event_loop_runner.moveToThread(event_loop_runner_thread)
    event_loop_runner_thread.started.connect(event_loop_runner.process_event_loop)

    progressBar = event_loop_runner.set_progress

    event_loop_runner_thread.start()

     
    app.setApplicationName("PrusaControl")
    app.setOrganizationName("Prusa Research")
    app.setOrganizationDomain("prusa3d.com")

    dpi = app.desktop().logicalDpiX()

    app.setWindowIcon(QIcon(base_dir + "data/icon/favicon.ico"))
    if dpi == 96:
        file = QFile(base_dir + "data/my_stylesheet.qss")
    #elif dpi == 72:
    #    file = QFile(base_dir + "data/my_stylesheet.qss")
    else:
        file = QFile(base_dir + "data/my_stylesheet_without_f.qss")
    file.open(QFile.ReadOnly)
    
    StyleSheet_tmp = str(file.readAll())
    if system_platform in ['Windows']:
        StyleSheet = StyleSheet_tmp.replace('base_dir', "")
    else:
        StyleSheet = StyleSheet_tmp.replace('base_dir', base_dir)

    if not system_platform in ['Windows', 'Linux']:
        app.setStyle(QStyleFactory.create("Windows"))
        
    app.setStyleSheet(StyleSheet)    



    #local_path = os.path.realpath(__file__)

    controller = Controller(app, base_dir, progressBar)
    progressBar(100)
    window = controller.get_view()

    event_loop_runner.is_running = False
    event_loop_runner_thread.quit()
    event_loop_runner_thread.wait()
    event_loop_runner.splash.finish(window)

    controller.check_version()
    app.installEventFilter(window)
    app.exec_()
    atexit.register(controller.write_config)



if __name__ == '__main__':
    system_platform = platform.system()
    log_path = "/"
    if system_platform in ['Windows']:
        log_path = "\\"
    else:
        log_path = "/"
    FORMAT = "[%(levelname)s][%(filename)s:%(lineno)s:%(funcName)s()]-%(message)s"

    if DEBUG:
        logging.basicConfig(filename=os.path.expanduser("~" + log_path + "prusacontrol.log"), format=FORMAT, filemode='w', level=logging.DEBUG)
        #cProfile.runctx('main()', globals(), locals(), 'prusacontrol.profile')
    else:
        logging.basicConfig(filename=os.path.expanduser("~" + log_path + "prusacontrol.log"), format=FORMAT, filemode='w', level=logging.WARNING)

    if DEBUG:
        cProfile.runctx('main()', globals(), locals(), 'prusacontrol.profile')
    else:
        main()
