# -*- coding: utf-8 -*-
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QScrollArea, QLayout, QAction, QMenu, QLineEdit, QFormLayout)

from PyQt5.QtWidgets import QColorDialog
from PyQt5.QtGui import QStandardItem

__author__ = 'Tibor Vavra'

import logging
import math
import os
from copy import deepcopy

import numpy as np
import time
#from OpenGL.GL import *
from PyQt5.QtCore import QFileInfo
from PyQt5.QtCore import QPropertyAnimation
from PyQt5.QtCore import QTextCodec

from PyQt5.QtCore import Qt, QSettings, QFile, QIODevice, QVariant, QEvent
from PyQt5.QtGui import QFont, QFontDatabase, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                             QProgressBar, QPushButton, QSizePolicy, QSpacerItem,
                             QVBoxLayout, QWidget,
                             QSlider, QStyleOptionSlider, QDialog, QDialogButtonBox,
                             QComboBox, QCheckBox, QApplication, QSpinBox,
                             QDoubleSpinBox, QFileDialog, QStyleFactory)

from PyQt5.QtWidgets import QScrollArea

from PyQt5.QtOpenGL import QGLWidget

import projectFile
import sceneRender

def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        print('%s function took %0.3f ms' % (f.func_name, (time2-time1)*1000.0))
        return ret
    return wrap

class Gcode_slider(QWidget):
    def __init__(self, other, controller):
        super(Gcode_slider, self).__init__()
        self.controller = controller
        self.initUI()

    def initUI(self):
        self.points = []
        self.init_points()

        self.rangeMin = 0.
        self.rangeMax = 0.


        self.max_label = QLabel(self)
        self.max_label.setObjectName("gcode_slider_max_label")
        #self.max_label.setFixedWidth(150)
        self.max_label.setText("Max")
        self.max_label.setAlignment(Qt.AlignCenter)
        self.min_label = QLabel(self)
        self.min_label.setObjectName("gcode_slider_min_label")
        self.min_label.setText("Min")
        self.min_label.setAlignment(Qt.AlignCenter)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        self.slider = QSlider()
        self.slider.setOrientation(Qt.Vertical)
        #self.slider.setFixedWidth(144)
        #self.connect(self.slider, SIGNAL("valueChanged(int)"), self.set_value_label)
        self.slider.valueChanged.connect(self.set_value_label)

        self.slider.setTickInterval(1)

        self.value_label = QLabel(self)
        self.value_label.setObjectName("gcode_slider_value_label")
        self.value_label.setVisible(False)
        self.value_label.setText(u"─  0.00mm")
        self.value_label.setFixedWidth((int)(70*self.controller.dpi_coef))

        self.add_button = QPushButton("", self)
        if self.controller.app_config.system_platform in ["Darwin"]:
            self.add_button.setStyle(QStyleFactory.create("Macintosh"))
        self.add_button.setObjectName("gcode_slider_add_button")
        self.add_button.setVisible(False)
        self.add_button.setFixedWidth((int)(20*self.controller.dpi_coef))
        self.add_button.setToolTip(self.tr("Add color change point"))

        self.add_button.clicked.connect(self.add_point)

        main_layout.addWidget(self.max_label)

        main_layout.addWidget(self.slider)

        main_layout.addWidget(self.min_label)

        self.setLayout(main_layout)


        self.style = QApplication.style()
        self.opt = QStyleOptionSlider()
        self.slider.initStyleOption(self.opt)

        self.set_value_label(0.00)


    def init_points(self):
        if self.points:
            for point in self.points:
                point['value'] = -1

                point['label'].setText('')
                point['label'].move(0,0)
                point['label'].setVisible(False)
                point['button'].move(0,0)
                point['button'].setVisible(False)

        else:
            for i in range(0, 20):
                label = QLabel(self)
                label.setObjectName("gcode_slider_point_label")
                label.setVisible(False)
                label.setFixedWidth((int)(60*self.controller.dpi_coef))
                button = QPushButton('', self)
                if self.controller.app_config.system_platform in ["Darwin"]:
                    button.setStyle(QStyleFactory.create("Macintosh"))
                button.setObjectName("gcode_slider_point_button")
                button.setVisible(False)
                button.setFixedWidth((int)(20*self.controller.dpi_coef))
                button.setToolTip(self.tr("Delete color change point"))

                self.points.append({'value': -1,
                                    'label': label,
                                    'button': button
                                    })

    def add_point(self):
        self.slider.initStyleOption(self.opt)

        rectHandle = self.style.subControlRect(self.style.CC_Slider, self.opt, self.style.SC_SliderHandle)
        myPoint = rectHandle.topRight() + self.slider.pos()

        value = self.slider.value()
        layer_value = self.controller.gcode.data_keys[value]

        #delete_button = QtGui.QPushButton("X", self)
        #delete_button.setFixedWidth(20)
        #self.point_label = QtGui.QLabel(self)
        number = 0


        for p in self.points:
            if p['value'] == layer_value:
                return

        for i, p in enumerate(self.points):
            number = i
            if p['value'] == -1:
                break

        self.points[number]['value'] = layer_value

        self.points[number]['button'].setVisible(True)
        self.points[number]['button'].move((int)(2*self.controller.dpi_coef), myPoint.y() - 9)
        self.points[number]['button'].clicked.connect(lambda: self.delete_point(number))

        self.points[number]['label'].setText(u"%smm ─" % layer_value)
        self.points[number]['label'].setVisible(True)
        self.points[number]['label'].move((int)(20*self.controller.dpi_coef), myPoint.y() - 9)

    def delete_point(self, number):
        self.points[number]['value'] = -1
        self.points[number]['button'].setVisible(False)
        self.points[number]['label'].setVisible(False)

    def set_value_label(self, value):
        self.slider.initStyleOption(self.opt)

        #rectHandle = style.subControlRect(QtGui.QStyle.CC_Slider, opt, QtGui.QStyle.SC_SliderHandle, self)
        rectHandle = self.style.subControlRect(self.style.CC_Slider, self.opt, self.style.SC_SliderHandle)
        myPoint = rectHandle.topRight() + self.slider.pos()

        if self.controller.gcode:
            layer_value = self.controller.gcode.data_keys[value]
        else:
            layer_value = "0.00"
        self.value_label.setText(u"─ %smm" % layer_value)
        self.value_label.move(self.slider.width() + (int)(75*self.controller.dpi_coef), myPoint.y() - 9)
        self.add_button.move(self.slider.width() + (int)(145*self.controller.dpi_coef), myPoint.y() - 9)

        if self.controller.is_multimaterial() and not self.controller.is_single_material_mode():
            self.add_button.setVisible(False)
        else:
            self.add_button.setVisible(True)
        self.value_label.setVisible(True)

    def setRange(self, rangeMin, rangeMax):
        self.rangeMin = rangeMin
        self.rangeMax = rangeMax
        self.max_label.setText("%.2fmm" % rangeMax)
        self.min_label.setText("%.2fmm" % rangeMin)

        self.slider.setRange(rangeMin, rangeMax)

    def setSingleStep(self, step):
        self.slider.setSingleStep(step)

    def setPageStep(self, step):
        self.slider.setPageStep(step)

    def setTickInterval(self, tick):
        self.slider.setTickInterval(tick)

    def setValue(self, value):
        self.value_label.setText(u"─ %3.2fmm" % value)
        #self.max_label.setText("%3.2fmm" % self.rangeMax)
        #self.min_label.setText("%3.2fmm" % self.rangeMin)

        self.slider.setValue(value)

    def setTickPosition(self, position):
        self.slider.setTickPosition(position)

    def setMinimum(self, minimum, minimum_label):
        self.rangeMin = minimum_label
        self.min_label.setText("%.2fmm" % self.rangeMin)
        #print(str(minimum))
        self.slider.setMinimum(minimum)

    def setMaximum(self, maximum, maximum_label):
        self.rangeMax = maximum_label
        self.max_label.setText("%.2fmm" % self.rangeMax)
        #print(str(maximum))
        self.slider.setMaximum(maximum)


    def get_color_change_layers(self):
        #return [[i['value'], self.controller.gcode.data[i['value']][0][-1]] for i in self.parent.gcode_slider.points if not i['value'] == -1]
        if self.controller.is_multimaterial() and not self.controller.is_single_material_mode():
            return []
        else:
            return [i['value'] for i in self.points if not i['value'] == -1]


class Spline_editor(QWidget):
    def __init__(self, other, controller):
        super(Spline_editor, self).__init__()
        self.controller = controller
        self.initUI()

    def initUI(self):
        self.data = np.zeros((11), dtype=np.float32)
        self.points = []
        #self.init_points()

        self.double_value = 0.0
        self.number_of_ticks = 10
        self.min = 0.0
        self.max = 1.0
        self.label_height = 0


        self.max_label = QLabel(self)
        self.max_label.setObjectName("gcode_slider_max_label")
        self.max_label.setText("Max")
        self.max_label.setAlignment(Qt.AlignCenter)

        '''
        self.minimal_detail_l = QtGui.QLabel(self)
        self.minimal_detail_l.setObjectName("gcode_slider_max_label")
        self.minimal_detail_l.setText(self.tr("Minimal detail"))
        self.minimal_detail_l.setAlignment(Qt.AlignCenter)

        self.maximal_detail_l = QtGui.QLabel(self)
        self.maximal_detail_l.setObjectName("gcode_slider_max_label")
        self.maximal_detail_l.setText(self.tr("Maximal detail"))
        self.maximal_detail_l.setAlignment(Qt.AlignCenter)


        top_labels_widget = QtGui.QWidget()
        top_labels_layout = QtGui.QHBoxLayout()
        top_labels_layout.setSpacing(0)
        top_labels_layout.setMargin(0)
        top_labels_layout.addWidget(self.minimal_detail_l)
        top_labels_layout.addWidget(self.max_label)
        top_labels_layout.addWidget(self.maximal_detail_l)
        top_labels_widget.setLayout(top_labels_layout)
        '''

        self.min_label = QLabel(self)
        self.min_label.setObjectName("spline_slider_min_label")
        self.min_label.setText("Min")
        self.min_label.setAlignment(Qt.AlignCenter)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        #main_layout.setSpacing(2)
        #main_layout.setMargin(2)

        self.slider = QSlider(parent=self)
        self.slider.setOrientation(Qt.Vertical)
        self.slider.setObjectName("spline_slider")
        self.slider.setFixedHeight(350)

        #self.connect(self.slider, pyqtSignal("valueChanged(int)"), self.set_value_label)
        self.slider.valueChanged.connect(self.set_value_label)

        self.value_label = QLabel(parent=self)
        self.value_label.setObjectName("spline_slider_value_label")
        self.value_label.setVisible(False)
        self.value_label.setText(u"─0.00mm")
        self.value_label.setFixedWidth(75)

        self.plus_button = QPushButton("", parent=self)
        self.plus_button.setAutoRepeat(True)
        self.plus_button.setObjectName("variable_hight_plus_button")
        self.plus_button.setVisible(False)
        self.plus_button.setFixedWidth(20)
        self.plus_button.clicked.connect(self.plus_value)

        self.minus_button = QPushButton("", parent=self)
        self.minus_button.setAutoRepeat(True)
        self.minus_button.setObjectName("variable_hight_minus_button")
        self.minus_button.setVisible(False)
        self.minus_button.setFixedWidth(20)
        self.minus_button.clicked.connect(self.minus_value)


        main_layout.addWidget(self.max_label)
        main_layout.addWidget(self.slider)
        main_layout.addWidget(self.min_label)

        self.setLayout(main_layout)

        self.style = QApplication.style()
        self.opt = QStyleOptionSlider()
        self.slider.initStyleOption(self.opt)

        self.label_height = self.max_label.height() -1


    def init_points(self):
        start_y = self.label_height
        end_y = 350.+self.label_height


        if self.points:
            for point in self.points:
                #TODO: set for other objects on scene
                pass
        else:
            for i in range(0, self.number_of_ticks+1):
                #first and last layer
                '''
                if i == 0:
                    value = i
                    y = start_y
                elif i == self.number_of_ticks-1:
                    value = i
                    y = end_y
                else:
                    value = 0
                    y = (400/self.number_of_ticks-1) * i
                '''
                y = (350./ (self.number_of_ticks)) * i + start_y
                #clear points values
                '''
                self.points.append({'value': 0,
                                    'detail' : 0.0,      #x value
                                    'y' : y
                                    })
                '''




    def compute_double_value(self, value):
        return ((self.max-self.min)/self.number_of_ticks) * value


    def set_model(self, mesh):
        self.mesh = mesh
        self.data = mesh.variable_layer_height_data

    def paintEvent(self, event):
        path = QPainterPath()
        start_y = self.label_height
        #path.moveTo(85, self.label_height)
        #path.moveTo(85, 400-self.label_height)

        #defined_points = [p for p in self.points if not p['value'] == -1]

        #if len(defined_points)>2:
        for i, p in enumerate(self.data):
            y = (350./ (self.number_of_ticks)) * i + start_y
            if i == 0:
                path.moveTo((p * 20.) + 85, y)
            else:
                path.lineTo((p * 20.) + 85, y)

            #path.cubicTo((defined_points[0]['detail'] * 10.) + 85, self.label_height,
            #            (defined_points[1]['detail'] * 10.) + 85, 200,
            #            (defined_points[2]['detail'] * 10.) + 85, 400-self.label_height)
        #else:
            #print("Count of height for point: " + str((((self.max-self.min)/self.number_of_ticks) * defined_points[0]['value'])))
        #    path.lineTo((defined_points[0]['detail']*10.)+85, self.label_height)
        #    path.lineTo((defined_points[1]['detail']*10.)+85, 350+self.label_height)

        #path.lineTo(100, 100)
        #path.lineTo(150, 150)
        #path.cubicTo(50, 50, 50, 50, 80, 80)
        #path.cubicTo(80, 80, 50, 50, 80, 80)
        pen01 = QPen(Qt.white)
        pen01.setWidthF(2.0)
        pen02 = QPen(Qt.green)
        pen03 = QPen(Qt.red)
        pen02.setWidthF(2.5)

        qp = QPainter()
        qp.begin(self)
        qp.setRenderHint(QPainter.Antialiasing)
        #grid
        qp.setPen(pen01)
        qp.drawLine(20, self.label_height, 160, self.label_height)
        qp.drawLine(20, self.label_height + 350, 160, 350 + self.label_height)
        qp.drawLine(20, self.label_height, 20, 350 + self.label_height)
        qp.drawLine(160, self.label_height, 160, 350 + self.label_height)

        #path
        qp.setPen(pen02)
        qp.drawPath(path)


        qp.end()


    def plus_value(self):
        #print("Slider plus")
        #TODO:read value from slider and increment quality for this layer
        slider_value = (self.number_of_ticks) - self.slider.value()
        #print(slider_value)
        for n, p in enumerate(self.data):
            if n == slider_value:
                if self.data[n] <= 0.99:
                    self.data[n] += 0.2
        #print(self.data)
        self.repaint()
        self.mesh.recalculate_texture()
        self.controller.update_scene()

    def minus_value(self):
        #print("Slider minus")
        # TODO:read value from slider and decrease quality for this layer
        slider_value = (self.number_of_ticks) - self.slider.value()
        #print(slider_value)
        for n, p in enumerate(self.data):
            if n == slider_value:
                if self.data[n] >= -0.99:
                    self.data[n] -= 0.2
        #print(self.data)
        self.repaint()
        self.mesh.recalculate_texture()
        self.controller.update_scene()


    def set_value_label(self, value):
        self.slider.initStyleOption(self.opt)

        rectHandle = self.style.subControlRect(self.style.CC_Slider, self.opt, self.style.SC_SliderHandle)
        myPoint = rectHandle.topRight() + self.slider.pos()

        self.double_value = ((self.max-self.min)/self.number_of_ticks) * value
        self.value_label.setText(u" ─ %3.2fmm" % self.double_value)
        self.value_label.move(self.slider.width() + 70, myPoint.y() - 9)
        self.plus_button.move(self.slider.width() + 25, myPoint.y() - 9)
        self.minus_button.move(self.slider.width(), myPoint.y() - 9)

        self.plus_button.setVisible(True)
        self.minus_button.setVisible(True)
        self.value_label.setVisible(True)

    def setRange(self, rangeMin, rangeMax):
        self.max_label.setText("%3.2f" % rangeMax)
        self.min_label.setText("%3.2f" % rangeMin)
        self.slider.setRange(rangeMin, rangeMax)

    def setSingleStep(self, step):
        self.slider.setSingleStep(step)

    def setPageStep(self, step):
        self.slider.setPageStep(step)

    def setTickInterval(self, tick):
        self.slider.setTickInterval(tick)

    def setValue(self, value):
        self.value_label.setText(u"─%3.2fmm" % value)
        self.slider.setValue(value)

    def setTickPosition(self, position):
        self.slider.setTickPosition(position)

    def set_number_of_ticks(self, number):
        self.number_of_ticks = number
        self.slider.setTickInterval(1)
        self.slider.setMaximum(number)
        self.init_points()

    def setMinimum(self, minimum):
        self.min = minimum
        self.min_label.setText("%.2fmm" % minimum)
        self.slider.setMinimum(0)

    def setMaximum(self, maximum):
        self.max = maximum
        self.max_label.setText("%.2fmm" % maximum)
        self.slider.setMaximum(10)


class SettingsDialog(QDialog):
    def __init__(self, controller, editable=True,  parent = None):
        super(SettingsDialog, self).__init__(controller.view, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)

        self.controller = controller

        layout = QVBoxLayout(self)

        # nice widget for editing the date
        self.language_label = QLabel(self.tr("Language"))
        self.language_combo = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.language_combo.setStyle(QStyleFactory.create('Windows'))
        #set enumeration
        self.language_combo.addItems(list(self.controller.enumeration['language'].values()))
        l = list(self.controller.enumeration['language'])
        self.language_combo.setCurrentIndex(l.index(self.controller.settings['language']))

        self.printer_label = QLabel(self.tr("Printer model"))
        self.printer_combo = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.printer_combo.setStyle(QStyleFactory.create('Windows'))
        self.printer_combo.addItems(self.controller.get_printers_labels_ls(only_visible=True))
        self.printer_combo.setCurrentIndex(self.controller.get_printers_names_ls(only_visible=True).index(self.controller.settings['printer']))
        self.printer_combo.currentIndexChanged.connect(self.update_printer_variations)

        self.printer_type_label = QLabel(self.tr("Printer variation"))
        self.printer_type_combo = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.printer_type_combo.setStyle(QStyleFactory.create('Windows'))
        ##
        labels, _f = self.controller.get_printer_variations_labels_ls(self.controller.actual_printer)
        self.printer_type_combo.addItems(labels)
        names, _ = self.controller.get_printer_variations_names_ls(self.controller.actual_printer)
        self.printer_type_combo.setCurrentIndex(names.index(self.controller.settings['printer_type']))

        self.debug_checkbox = QCheckBox(self.tr("Debug"))
        self.debug_checkbox.setChecked(self.controller.settings['debug'])

        self.automatic_placing_checkbox = QCheckBox(self.tr("Automatic placing"))
        self.automatic_placing_checkbox.setChecked(self.controller.settings['automatic_placing'])

        self.analyze_checkbox = QCheckBox(self.tr("Analyzer"))
        self.analyze_checkbox.setChecked(self.controller.settings['analyze'])

        self.update_parameters_checkbox = QCheckBox(self.tr("Auto update parameters"))
        self.update_parameters_checkbox.setChecked(self.controller.settings['automatic_update_parameters'])

        layout.addWidget(self.language_label)
        layout.addWidget(self.language_combo)

        layout.addWidget(self.printer_label)
        layout.addWidget(self.printer_combo)

        layout.addWidget(self.printer_type_label)
        layout.addWidget(self.printer_type_combo)

        layout.addWidget(self.debug_checkbox)
        layout.addWidget(self.automatic_placing_checkbox)
        layout.addWidget(self.analyze_checkbox)
        layout.addWidget(self.update_parameters_checkbox)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        if not editable:
            ok_button = buttons.button(QDialogButtonBox.Ok)
            ok_button.setEnabled(False)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_printer_variations(self):
        self.printer_type_combo.clear()
        labels_lst, first = self.controller.get_printer_variations_labels_ls(self.controller.get_printers_names_ls(only_visible=True)[self.printer_combo.currentIndex()])
        self.printer_type_combo.addItems(labels_lst)
        self.printer_type_combo.setCurrentIndex(first)



    @staticmethod
    def get_settings_data(controller, editable=True, parent = None):
        data = deepcopy(controller.settings)
        dialog = SettingsDialog(controller, editable, parent)
        dialog.setWindowTitle("Settings")
        result = dialog.exec_()
        data['language'] = list(controller.enumeration['language'])[dialog.language_combo.currentIndex()]
        data['printer'] = controller.get_printers_names_ls(only_visible=True)[dialog.printer_combo.currentIndex()]
        printer_variations, _f = controller.get_printer_variations_names_ls(data['printer'])
        data['printer_type'] = printer_variations[dialog.printer_type_combo.currentIndex()]

        data['debug'] = dialog.debug_checkbox.isChecked()
        data['automatic_placing'] = dialog.automatic_placing_checkbox.isChecked()
        data['analyze'] = dialog.analyze_checkbox.isChecked()
        data['automatic_update_parameters'] = dialog.update_parameters_checkbox.isChecked()
        return (data, result == QDialog.Accepted)


class NewOctoPrintDialog(QDialog):
    def __init__(self, controller):
        super(NewOctoPrintDialog, self).__init__(controller.view, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)

        self.controller = controller

        layout = QFormLayout(self)

        # nice widget for editing the date
        self.name_label = QLabel(self.tr("Name"))
        self.name_edit = QLineEdit()

        self.ip_address_label = QLabel(self.tr("IP"))
        self.ip_address_edit = QLineEdit()

        self.apikey_label = QLabel(self.tr("ApiKey"))
        self.apikey_edit = QLineEdit()

        #self.username_label = QLabel(self.tr("User"))
        #self.username_edit = QLineEdit()

        #self.password_label = QLabel(self.tr("Password"))
        #self.password_edit = QLineEdit()

        layout.addRow(self.name_label, self.name_edit)
        layout.addRow(self.ip_address_label, self.ip_address_edit)
        layout.addRow(self.apikey_label, self.apikey_edit)
        #layout.addRow(self.username_label, self.username_edit)
        #layout.addRow(self.password_label, self.password_edit)

        # OK and Cancel buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)



    @staticmethod
    def get_settings_data(controller, ):
        data = {}
        dialog = NewOctoPrintDialog(controller)
        dialog.setWindowTitle("New OctoPrint service")
        result = dialog.exec_()

        data['name'] = dialog.name_edit.text()
        data['ip'] = dialog.ip_address_edit.text()
        data['apikey'] = dialog.apikey_edit.text()
        #data['user'] = dialog.username_edit.text()
        #data['password'] = dialog.password_edit.text()


        return (data, result == QDialog.Accepted)


class FirmwareUpdateDialog(QDialog):
    def __init__(self, controller, parent = None):
        super(FirmwareUpdateDialog, self).__init__(parent)

        self.controller = controller
        #self.differentVersion = True
        #self.actualVersion = '1.0.2'
        #self.yourVersion = '1.0.1'

        layout = QVBoxLayout(self)


        #self.actualVersionLabel = QtGui.QLabel("Actual version of firmware is %s" % self.actualVersion)
        #self.yourVersionLabel = QtGui.QLabel("Your version of firmware is %s" % self.yourVersion)

        self.open_file_button = QPushButton(self.tr("Open file"))

        self.update_button = QPushButton(self.tr("Update"))
        #TODO:Doplnit
        #self.updateButton.clicked.connect(self.controller.updateFirmware)
        #self.updateButton.setEnabled(self.differentVersion)

        #layout.addWidget(self.actualVersionLabel)
        #layout.addWidget(self.yourVersionLabel)
        layout.addWidget(self.open_file_button)
        layout.addWidget(self.update_button)

        # Close button
        buttons = QDialogButtonBox(
            QDialogButtonBox.Close,
            Qt.Horizontal, self)
        buttons.clicked.connect(self.close)
        layout.addWidget(buttons)

    @staticmethod
    def get_firmware_update(controller, parent = None):
        dialog = FirmwareUpdateDialog(controller, parent)
        dialog.setWindowTitle("Firmware update")
        result = dialog.exec_()
        data = {'msg': 'Update is complete. New version is ....'}
        return (data, result == QDialog.Accepted)


class AboutDialog(QDialog):
    def __init__(self, controller, parent = None):
        super(AboutDialog, self).__init__(parent)

        self.controller = controller
        self.different_version = True
        #self.actual_version = '1.0.2'
        self.your_version = self.controller.app_config.version
        self.slic3r_version = self.controller.slicer_manager.get_version()

        layout = QVBoxLayout(self)

        self.prusa_control_label = QLabel("PrusaControl")
        self.prusa_control_label.setAlignment(Qt.AlignCenter)

        self.prusa_control_text = QLabel(controller.view.tr("PrusaControl\nTibor Vavra, Prusa Research\nDominik Cisar, Prusa Research\n\nSlic3r engine\nVojtech Bubnik, Prusa Research\nAlessandro Ranellucci"))



        self.local_version_label = QLabel(controller.view.tr("PrusaControl version is ") + str(self.your_version))
        self.slic3r_engine_version_label = QLabel(controller.view.tr("Slic3r engine version is ") + str(self.slic3r_version))


        #self.check_version_button = QtGui.QPushButton(self.tr("Check version"))
        #TODO:Doplnit
        #self.checkVersionButton.clicked.connect(self.controller.checkVersion)
        #self.checkVersionButton.setEnabled(self.differentVersion)

        layout.addWidget(self.prusa_control_label)
        layout.addWidget(self.prusa_control_text)

        layout.addWidget(self.local_version_label)
        layout.addWidget(self.slic3r_engine_version_label)
        #layout.addWidget(self.check_version_button)

        # Close button
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok,
            Qt.Horizontal, self)
        buttons.clicked.connect(self.close)
        layout.addWidget(buttons)

    @staticmethod
    def get_about_dialog(controller, parent = None):
        dialog = AboutDialog(controller, parent)
        dialog.setWindowTitle(controller.view.tr("About"))
        result = dialog.exec_()
        data = {'msg':'Update is complete. New version is ....'}
        return (data, result == QDialog.Accepted)


class PrinterInfoDialog(QDialog):
    def __init__(self, controller, parent= None):
        super(PrinterInfoDialog, self).__init__(parent)

        self.controller = controller
        self.printer_name = self.controller.get_printer_name()
        self.your_firmware_version = self.controller.get_firmware_version_number()

        layout = QVBoxLayout(self)

        self.printerNameLabel = QLabel(controller.view.tr("Your printer is") + " %s" % self.printer_name)

        self.printerFirmwareText = QLabel(controller.view.tr("Version of firmware is") + " %s" % self.your_firmware_version)


        #TODO:Doplnit
        #self.checkVersionButton.clicked.connect(self.controller.checkVersion)
        #self.checkVersionButton.setEnabled(self.differentVersion)

        layout.addWidget(self.printerNameLabel)
        layout.addWidget(self.printerFirmwareText)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok,
            Qt.Horizontal, self)
        buttons.clicked.connect(self.close)
        layout.addWidget(buttons)

    @staticmethod
    def get_printer_info_dialog(controller, parent = None):
        dialog = PrinterInfoDialog(controller, parent)
        dialog.setWindowTitle("Printer info")
        result = dialog.exec_()
        data = {'msg': 'Update is complete. New version is ....'}
        return (data, result == QDialog.Accepted)


class PrusaControlView(QMainWindow):
    def __init__(self, c):
        self.controller = c
        super(PrusaControlView, self).__init__()

        #print("initialization of PrusaControlView")
        self.settings = QSettings("Prusa Research", "PrusaControl")
        self.restoreGeometry(self.settings.value("geometry", b''))
        self.restoreState(self.settings.value("windowState", b''))

        #print("font load of PrusaControlView")
        font_id = QFontDatabase.addApplicationFont(self.controller.app_config.local_path + "data/font/TitilliumWeb-Light.ttf")
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        self.font = QFont(font_family)
        self.setFont(self.font)

        #print("enable of Drop")
        self.setAcceptDrops(True)

        self.is_setting_panel_opened = True

        self.setObjectName('PrusaControlView')


        self.infillValue = 20
        self.changable_widgets = {}

        self.object_id = 0

        self.setVisible(False)
        #print("creating of widgets")

        self.centralWidget = QWidget(self)
        self.object_settings_panel = None

        self.menubar = self.menuBar()
        #print("menu bar")

        #self.create_menu()

        #self.prusa_control_widget = PrusaControlWidget(self)

        self.glWidget = sceneRender.GLWidget(self)
        self.glWidget.setObjectName('glWidget')
        #print("GL widgets")

        #Object settings layout
        #self.object_groupbox_layout = QtGui.QFormLayout()

        self.object_group_box = QGroupBox()
        self.object_group_box.setObjectName('object_group_box')

        self.object_variable_layer_box = QGroupBox()
        self.object_variable_layer_box.setObjectName('object_variable_layer_box')

        self.gcode_group_box = QGroupBox()
        self.gcode_group_box.setObjectName('gcode_group_box')


        #print("right menu")
        self.name_l = QLabel(self.object_group_box)
        self.name_l.setObjectName("name_l")

        self.object_extruder_l = QLabel("", self.object_group_box)
        self.object_extruder_l.setObjectName("object_extruder_l")
        self.object_extruder_c = QComboBox(self.object_group_box)
        if self.controller.app_config.system_platform in ['Linux']:
            self.object_extruder_c.setStyle(QStyleFactory.create('Windows'))
        self.object_extruder_c.setObjectName("object_extruder_c")

        self.object_extruder_c.insertItems(4, ['Extruder 1', 'Extruder 2', 'Extruder 3', 'Extruder 4'])
        self.object_extruder_c.setCurrentIndex(0)

        self.object_extruder_c.currentIndexChanged.connect(lambda: self.set_extruder_on_object(self.object_extruder_c,
                                                                                               self.get_object_id()))


        self.filename_label = QLabel("", self.object_group_box)
        self.filename_label.setObjectName("filename_label")
        self.filename_c = QComboBox(self.object_group_box)
        if self.controller.app_config.system_platform in ['Linux']:
            self.filename_c.setStyle(QStyleFactory.create('Windows'))
        self.filename_c.setObjectName("filename_c")
        self.filename_c.setVisible(False)

        self.filename_c.currentIndexChanged.connect(lambda: self.select_model_by_filename(self.filename_c.currentText()))
        #TODO: Add logic for selecting different part from combobox




        self.position_l = QLabel("", self.object_group_box)
        self.position_l.setObjectName("position_l")
        self.edit_pos_x = QSpinBox(self.object_group_box)
        self.edit_pos_x.setObjectName("edit_pos_x")
        self.edit_pos_x.setMaximum(200)
        self.edit_pos_x.setMinimum(-200)
        self.edit_pos_x.setSuffix("mm")
        self.edit_pos_x.valueChanged.connect(lambda: self.set_position_on_object(self.edit_pos_x,
                                                                                 self.get_object_id(),
                                                                                 self.edit_pos_x.value(),
                                                                                 self.edit_pos_y.value(),
                                                                                 self.edit_pos_z.value(),
                                                                                 self.place_on_zero.isChecked()))

        self.edit_pos_y = QSpinBox(self.object_group_box)
        self.edit_pos_y.setObjectName("edit_pos_y")
        self.edit_pos_y.setMaximum(200)
        self.edit_pos_y.setMinimum(-200)
        self.edit_pos_y.setSuffix("mm")
        self.edit_pos_y.valueChanged.connect(lambda: self.set_position_on_object(self.edit_pos_y,
                                                                                 self.get_object_id(),
                                                                                 self.edit_pos_x.value(),
                                                                                 self.edit_pos_y.value(),
                                                                                 self.edit_pos_z.value(),
                                                                                 self.place_on_zero.isChecked()))

        self.edit_pos_z = QSpinBox(self.object_group_box)
        self.edit_pos_z.setObjectName("edit_pos_z")
        self.edit_pos_z.setMaximum(300)
        self.edit_pos_z.setMinimum(-50)
        self.edit_pos_z.setSuffix("mm")
        self.edit_pos_z.valueChanged.connect(lambda: self.set_position_on_object(self.edit_pos_z,
                                                                                 self.get_object_id(),
                                                                                 self.edit_pos_x.value(),
                                                                                 self.edit_pos_y.value(),
                                                                                 self.edit_pos_z.value(),
                                                                                 self.place_on_zero.isChecked()))

        self.rotation_l = QLabel("", self.object_group_box)
        self.rotation_l.setObjectName("rotation_l")
        self.edit_rot_x = QSpinBox(self.object_group_box)
        self.edit_rot_x.setObjectName("edit_rot_x")
        self.edit_rot_x.setMaximum(360)
        self.edit_rot_x.setMinimum(-360)
        self.edit_rot_x.setSuffix(u"°")
        self.edit_rot_x.valueChanged.connect(lambda: self.set_rotation_on_object(self.edit_rot_x,
                                                                                 self.get_object_id(),
                                                                                 self.edit_rot_x.value(),
                                                                                 self.edit_rot_y.value(),
                                                                                 self.edit_rot_z.value(),
                                                                                 self.place_on_zero.isChecked()))

        self.edit_rot_y = QSpinBox(self.object_group_box)
        self.edit_rot_y.setObjectName("edit_rot_y")
        self.edit_rot_y.setMaximum(360)
        self.edit_rot_y.setMinimum(-360)
        self.edit_rot_y.setSuffix(u"°")
        self.edit_rot_y.valueChanged.connect(lambda: self.set_rotation_on_object(self.edit_rot_y,
                                                                                 self.get_object_id(),
                                                                                 self.edit_rot_x.value(),
                                                                                 self.edit_rot_y.value(),
                                                                                 self.edit_rot_z.value(),
                                                                                 self.place_on_zero.isChecked()))

        self.edit_rot_z = QSpinBox(self.object_group_box)
        self.edit_rot_z.setObjectName("edit_rot_z")
        self.edit_rot_z.setMaximum(360)
        self.edit_rot_z.setMinimum(-360)
        self.edit_rot_z.setSuffix(u"°")
        self.edit_rot_z.valueChanged.connect(lambda: self.set_rotation_on_object(self.edit_rot_z,
                                                                                 self.get_object_id(),
                                                                                 self.edit_rot_x.value(),
                                                                                 self.edit_rot_y.value(),
                                                                                 self.edit_rot_z.value(),
                                                                                 self.place_on_zero.isChecked()))

        self.scale_l = QLabel("", self.object_group_box)
        self.scale_l.setObjectName("scale_l")
        self.edit_scale_x = QDoubleSpinBox(self.object_group_box)
        self.edit_scale_x.setObjectName("edit_scale_x")
        self.edit_scale_x.setMaximum(9999)
        self.edit_scale_x.setMinimum(-999)
        self.edit_scale_x.setSuffix("%")
        self.edit_scale_x.setDecimals(0)
        self.edit_scale_x.valueChanged.connect(lambda: self.set_scale_on_object(self.edit_scale_x,
                                                                                'x',
                                                                                self.get_object_id(),
                                                                                self.edit_scale_x.value(),
                                                                                self.edit_scale_y.value(),
                                                                                self.edit_scale_z.value(),
                                                                                self.place_on_zero.isChecked()))

        self.edit_scale_y = QDoubleSpinBox(self.object_group_box)
        self.edit_scale_y.setObjectName("edit_scale_y")
        self.edit_scale_y.setMaximum(9999)
        self.edit_scale_y.setMinimum(-999)
        self.edit_scale_y.setSuffix("%")
        self.edit_scale_y.setDecimals(0)
        self.edit_scale_y.valueChanged.connect(lambda: self.set_scale_on_object(self.edit_scale_y,
                                                                                'y',
                                                                                self.get_object_id(),
                                                                                self.edit_scale_x.value(),
                                                                                self.edit_scale_y.value(),
                                                                                self.edit_scale_z.value(),
                                                                                self.place_on_zero.isChecked()))

        self.edit_scale_z = QDoubleSpinBox(self.object_group_box)
        self.edit_scale_z.setObjectName("edit_scale_z")
        self.edit_scale_z.setMaximum(9999)
        self.edit_scale_z.setMinimum(-999)
        self.edit_scale_z.setSuffix("%")
        self.edit_scale_z.setDecimals(0)
        self.edit_scale_z.valueChanged.connect(lambda: self.set_scale_on_object(self.edit_scale_z,
                                                                                'z',
                                                                                self.get_object_id(),
                                                                                self.edit_scale_x.value(),
                                                                                self.edit_scale_y.value(),
                                                                                self.edit_scale_z.value(),
                                                                                self.place_on_zero.isChecked()))
        self.combobox_scale_units = QComboBox(self.object_group_box)
        if self.controller.app_config.system_platform in ['Linux']:
            self.combobox_scale_units.setStyle(QStyleFactory.create('Windows'))
        self.combobox_scale_units.setObjectName("combobox_scale_units")
        self.combobox_scale_units.addItems(["%", "mm"])
        self.combobox_scale_units.setCurrentIndex(0)

        self.scale_units = self.combobox_scale_units.currentText()
        self.combobox_scale_units.currentIndexChanged.connect(self.change_scale_units)

        self.lock_scale_axes_checkbox = QCheckBox("")
        self.lock_scale_axes_checkbox.setObjectName("lock_axis_checkbox")
        self.lock_scale_axes_checkbox.stateChanged.connect(self.lock_scale_axes_change)
        self.lock_scale_axes_checkbox.setChecked(True)

        self.place_on_zero = QCheckBox("", self.object_group_box)
        self.place_on_zero.setChecked(True)
        self.place_on_zero.setObjectName("place_on_zero")
        self.place_on_zero.stateChanged.connect(self.place_on_zero_changed)

        self.x_pos_l = QLabel('X', self.object_group_box)
        self.x_pos_l.setAlignment(Qt.AlignRight)
        self.x_pos_l.setObjectName("x_pos_l")
        self.y_pos_l = QLabel('Y', self.object_group_box)
        self.y_pos_l.setAlignment(Qt.AlignRight)
        self.y_pos_l.setObjectName("y_pos_l")
        self.z_pos_l = QLabel('Z', self.object_group_box)
        self.z_pos_l.setAlignment(Qt.AlignRight)
        self.z_pos_l.setObjectName("z_pos_l")

        self.x_rot_l = QLabel('X', self.object_group_box)
        self.x_rot_l.setAlignment(Qt.AlignRight)
        self.x_rot_l.setObjectName("x_rot_l")
        self.y_rot_l = QLabel('Y', self.object_group_box)
        self.y_rot_l.setAlignment(Qt.AlignRight)
        self.y_rot_l.setObjectName("y_rot_l")
        self.z_rot_l = QLabel('Z', self.object_group_box)
        self.z_rot_l.setAlignment(Qt.AlignRight)
        self.z_rot_l.setObjectName("z_rot_l")

        self.x_scale_l = QLabel('X', self.object_group_box)
        self.x_scale_l.setAlignment(Qt.AlignRight)
        self.x_scale_l.setObjectName("x_scale_l")
        self.y_scale_l = QLabel('Y', self.object_group_box)
        self.y_scale_l.setAlignment(Qt.AlignRight)
        self.y_scale_l.setObjectName("y_scale_l")
        self.z_scale_l = QLabel('Z', self.object_group_box)
        self.z_scale_l.setAlignment(Qt.AlignRight)
        self.z_scale_l.setObjectName("z_scale_l")

        self.units_l = QLabel("", self.object_group_box)
        self.units_l.setAlignment(Qt.AlignRight)
        self.units_l.setObjectName("units_l")
        self.lock_scale_axes_l = QLabel()
        self.lock_scale_axes_l.setAlignment(Qt.AlignRight)
        self.lock_scale_axes_l.setObjectName("lock_scale_axes_l")
        self.place_on_zero_l = QLabel("", self.object_group_box)
        self.place_on_zero_l.setObjectName("place_on_zero_l")

        self.advance_settings_b = QPushButton("", self.object_group_box)
        self.advance_settings_b.setObjectName("advance_settings_b")
        self.advance_settings_b.clicked.connect(self.controller.set_advance_settings)
        if self.controller.development_flag:
            self.advance_settings_b.setVisible(True)
        else:
            self.advance_settings_b.setVisible(False)
        # Object settings layout

        # Object variable layer widget
        self.variable_layer_widget = Spline_editor(self, self.controller)
        self.variable_layer_widget.setObjectName("variable_layer_widget")
        self.variable_layer_widget.setFixedHeight((int)(400*self.controller.dpi_coef))
        #self.connect(self.variable_layer_widget.slider, SIGNAL("valueChanged(int)"), self.set_variable_layer_slider)
        self.variable_layer_widget.slider.valueChanged.connect(self.set_variable_layer_slider)

        self.basic_settings_b = QPushButton()
        self.basic_settings_b.setObjectName("basic_settings_b")
        self.basic_settings_b.clicked.connect(self.controller.set_basic_settings)
        # Object variable layer widget

        # Gcode view layout
        #self.gcode_view_layout = QtGui.QVBoxLayout()

        self.color_change_l = QLabel()
        self.color_change_l.setObjectName("color_change_l")

        self.gcode_help_b= QPushButton("?", self.gcode_group_box)
        self.gcode_help_b.setCheckable(True)
        if self.controller.app_config.system_platform in ["Darwin"]:
            self.gcode_help_b.setStyle(QStyleFactory.create("Macintosh"))
        else:
            self.gcode_help_b.setFixedHeight((int)(19 * self.controller.dpi_coef))
            self.gcode_help_b.setFixedWidth((int)(19 * self.controller.dpi_coef))
        self.gcode_help_b.setObjectName("gcode_help_b")
        self.gcode_help_b.clicked.connect(self.controller.set_gcode_help_button_pressed)
        #self.gcode_help_b.released.connect(self.controller.set_gcode_help_button_released)
        #self.gcode_help_b.setToolTip("<img src=':img.png'>")



        self.gcode_slider = self.create_slider(self.set_gcode_slider, 0, 0, 100 ,Qt.Vertical, Gcode_slider)
        self.gcode_slider.setObjectName("gcode_slider")

        self.gcode_back_b = QPushButton()
        self.gcode_back_b.setObjectName("gcode_back_b")
        self.gcode_back_b.clicked.connect(self.controller.set_model_edit_view)
        self.gcode_back_b.setVisible(False)
        # Gcode view layout

        self.right_panel = QWidget(self)
        self.right_panel.setObjectName('right_panel')
        #self.right_panel_layout = QtGui.QFormLayout()
        self.right_panel_layout = QVBoxLayout()
        self.right_panel_layout.setObjectName('right_panel_layout')
        #self.right_panel_layout.setSpacing(5)
        self.right_panel_layout.setContentsMargins(0, 0, 0, 0)
        #self.right_panel_layout.setMargin(0)
        #self.right_panel_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea(self)

        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff )
        #self.scroll_area.setWidget(self.right_panel)

        #QAbstractScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff )

        self.printer_settings_l = QLabel()
        self.printer_settings_l.setObjectName('printer_settings_l')
        # print tab
        self.materialLabel = QLabel()
        self.materialLabel.setObjectName('materialLabel')
        self.materialCombo = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.materialCombo.setStyle(QStyleFactory.create('Windows'))
        self.materialCombo.setObjectName('materialCombo')
        material_label_ls, first = self.controller.get_printer_materials_labels_ls(self.controller.get_actual_printer())
        self.materialCombo.addItems(material_label_ls)
        self.materialCombo.setCurrentIndex(first)
        self.materialCombo.currentIndexChanged.connect(self.controller.update_gui)
        self.materialCombo.setMaxVisibleItems(len(material_label_ls))


        self.qualityLabel = QLabel()
        self.qualityLabel.setObjectName('qualityLabel')
        self.qualityCombo = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.qualityCombo.setStyle(QStyleFactory.create('Windows'))
        self.qualityCombo.setObjectName('qualityCombo')

        #self.infillLabel = QtGui.QLabel(self.tr("Infill") + " %s" % str(self.infillValue) + '%')
        #self.infillLabel.setObjectName('infillLabel')
        #self.infillLabel.setFixedWidth(75)
        #self.infillSlider = self.create_slider(self.set_infill, self.infillValue)
        #self.infillSlider.setObjectName('infillSlider')

        self.infillLabel = QLabel()
        self.infillLabel.setObjectName('infillLabel')
        self.infillLabel.setFixedWidth((int)(75*self.controller.dpi_coef))
        self.infillCombo = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.infillCombo.setStyle(QStyleFactory.create('Windows'))
        self.infillCombo.setObjectName('infillCombo')
        infill_ls, f = self.controller.get_infill_ls_and_index_of_default("0%")
        self.infillCombo.insertItems(len(infill_ls), infill_ls)
        self.infillCombo.setMaxVisibleItems(len(infill_ls))


        #self.supportCheckBox = QtGui.QCheckBox(self.tr("Support material"))
        self.supportLabel = QLabel()
        self.supportLabel.setObjectName('supportLabel')
        self.supportCombo = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.supportCombo.setStyle(QStyleFactory.create('Windows'))
        self.supportCombo.addItems([self.tr("None"), self.tr("Build plate only"), self.tr("Everywhere")])
        self.supportCombo.setObjectName('supportCombo')
        self.supportCombo.setMaxVisibleItems(10)

        self.brim_label = QLabel()
        self.brim_label.setObjectName('brim_label')
        self.brimCheckBox = QCheckBox("")
        self.brimCheckBox.setObjectName('brimCheckBox')


        #multimaterial settings
        self.single_material_mode_tooltip = self.tr("Do you want to print only from one material?")
        self.single_material_mode_checkbox = QCheckBox("Single material Mode")
        self.single_material_mode_checkbox.setObjectName("single_material_mode_checkbox")
        self.single_material_mode_checkbox.setToolTip(self.single_material_mode_tooltip)
        self.single_material_mode_checkbox.stateChanged.connect(self.controller.set_unset_single_material_mode)

        self.materials_settings_l = QLabel()
        self.materials_settings_l.setObjectName("materials_settings_l")

        self.extruder1_cb = QPushButton()
        self.extruder1_color = QColor.fromRgb(255, 170, 85)
        self.extruder1_cb.setObjectName("extruder1_cb")
        self.extruder1_cb.clicked.connect(self.controller.open_color_pick_dialog1)
        self.extruder1_l = QLabel()
        self.extruder1_l.setObjectName("extruder1_l")

        self.extruder1_c = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.extruder1_c.setStyle(QStyleFactory.create('Windows'))
        self.extruder1_c.addItems(material_label_ls)
        self.extruder1_c.setCurrentIndex(first)
        self.extruder1_c.currentIndexChanged.connect(self.update_material_settings)
        self.extruder1_c.setObjectName("extruder1_c")
        self.extruder1_c.setMaxVisibleItems(len(material_label_ls))

        self.extruder2_cb = QPushButton()
        self.extruder2_color = QColor.fromRgb(81, 130, 219)
        self.extruder2_cb.setObjectName("extruder2_cb")
        self.extruder2_cb.clicked.connect(self.controller.open_color_pick_dialog2)
        self.extruder2_l = QLabel()
        self.extruder2_l.setObjectName("extruder2_l")
        self.extruder2_c = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.extruder2_c.setStyle(QStyleFactory.create('Windows'))
        self.extruder2_c.addItems(material_label_ls)
        self.extruder2_c.setCurrentIndex(first)
        self.extruder2_c.currentIndexChanged.connect(self.update_material_settings)
        self.extruder2_c.setObjectName("extruder2_c")
        self.extruder2_c.setMaxVisibleItems(len(material_label_ls))

        self.extruder3_cb = QPushButton()
        self.extruder3_color = QColor.fromRgb(78, 205, 211)
        self.extruder3_cb.setObjectName("extruder3_cb")
        self.extruder3_cb.clicked.connect(self.controller.open_color_pick_dialog3)
        self.extruder3_l = QLabel()
        self.extruder3_l.setObjectName("extruder3_l")
        self.extruder3_c = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.extruder3_c.setStyle(QStyleFactory.create('Windows'))
        self.extruder3_c.addItems(material_label_ls)
        self.extruder3_c.setCurrentIndex(first)
        self.extruder3_c.currentIndexChanged.connect(self.update_material_settings)
        self.extruder3_c.setObjectName("extruder3_c")
        self.extruder3_c.setMaxVisibleItems(len(material_label_ls))

        self.extruder4_cb = QPushButton()
        self.extruder4_color = QColor.fromRgb(251, 114, 89)
        self.extruder4_cb.setObjectName("extruder4_cb")
        self.extruder4_cb.clicked.connect(self.controller.open_color_pick_dialog4)
        self.extruder4_l = QLabel()
        self.extruder4_l.setObjectName("extruder4_l")
        self.extruder4_c = QComboBox()
        if self.controller.app_config.system_platform in ['Linux']:
            self.extruder4_c.setStyle(QStyleFactory.create('Windows'))
        self.extruder4_c.addItems(material_label_ls)
        self.extruder4_c.setCurrentIndex(first)
        self.extruder4_c.currentIndexChanged.connect(self.update_material_settings)
        self.extruder4_c.setObjectName("extruder4_c")
        self.extruder4_c.setMaxVisibleItems(len(material_label_ls))

        self.used_extruder_tooltip = self.tr("Extruder is used")

        self.wipe_tower_tooltip = self.tr("Amount of material in wipe tower, material clearing")
        self.wipe_tower_l = QLabel()
        self.wipe_tower_l.setObjectName("wipe_tower_l")
        self.wipe_tower_l.setToolTip(self.wipe_tower_tooltip)
        self.wipe_tower_c = QComboBox()
        self.wipe_tower_c.setToolTip(self.wipe_tower_tooltip)
        if self.controller.app_config.system_platform in ['Linux']:
            self.wipe_tower_c.setStyle(QStyleFactory.create('Windows'))
        self.wipe_tower_c.setObjectName("wipe_tower_c")
        self.wipe_tower_c.addItems(self.get_list_of_wipe_tower_labels())
        self.wipe_tower_c.setCurrentIndex(1)
        self.wipe_tower_c.currentIndexChanged.connect(self.change_of_wipe_tower_settings)
        self.wipe_tower_c.setMaxVisibleItems(len(self.get_list_of_wipe_tower_labels()))
        # multimaterial settings


        self.object_settings_layout = self.create_object_settings_layout()
        self.object_group_box.setLayout(self.object_settings_layout)
        self.object_group_box.setEnabled(False)
        self.transformation_reset_b = QPushButton("", self.object_group_box)
        if self.controller.app_config.system_platform in ["Darwin"]:
            self.transformation_reset_b.setStyle(QStyleFactory.create("Macintosh"))
        else:
            self.transformation_reset_b.setFixedHeight((int)(19 * self.controller.dpi_coef))
            self.transformation_reset_b.setFixedWidth((int)(19 * self.controller.dpi_coef))
        self.transformation_reset_b.setObjectName("transformation_reset_b")
        self.transformation_reset_b.clicked.connect(lambda: self.reset_transformation_on_object(self.get_object_id()))


        self.object_variable_layer_box.setLayout(self.create_object_advance_settings_layout())
        self.object_variable_layer_box.setVisible(False)


        self.gcode_group_box.setLayout(self.create_gcode_view_layout())
        self.gcode_group_box.setVisible(False)

        self.progressBar = QProgressBar()
        self.progressBar.setObjectName('progressBar')
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum((int)(100*self.controller.dpi_coef))
        self.progressBar.setValue(0)
        self.progressBar.setAlignment(Qt.AlignCenter)
        #self.progressBar.setFormat("Generovani GCodu %p%")

        self.generateButton = QPushButton()
        self.generateButton.setObjectName('generateButton')
        self.generateButton.clicked.connect(self.controller.generate_button_pressed)
        self.generateButton.setEnabled(False)

        saveBWLayout = QHBoxLayout()
        saveBWLayout.setSpacing(0)
        self.saveMenuButton = QPushButton()
        self.saveMenuButton.setObjectName("saveMenuButton")
        self.saveButton = QPushButton(self.tr("Save G-Code"))
        self.saveButton.setObjectName("saveButton")
        self.saveButton.clicked.connect(self.controller.generate_button_pressed)

        self.saveMenu = QMenu()
        self.saveMenu.setObjectName("saveMenu")

        #self.saveMenu.addActions(self.get_actual_action_list(self.saveButton))

        self.update_actions_in_menu()
        self.saveMenuButton.setMenu(self.saveMenu)

        saveBWLayout.addWidget(self.saveButton)
        saveBWLayout.addWidget(self.saveMenuButton)
        saveBWLayout.setContentsMargins(0, 0, 0, 0)
        self.saveBW = QWidget()
        self.saveBW.setLayout(saveBWLayout)
        self.saveBW.setObjectName('saveBW')
        self.saveBW.setVisible(False)

        #self.right_panel_layout.setAlignment(Qt.AlignTop)
        printing_mm_parameters_layout = QGridLayout()
        printing_parameters_layout = QGridLayout()
        #printing_parameters_layout.setRowMinimumHeight(0, 65)

        printing_mm_parameters_layout.setColumnMinimumWidth(0, 10)
        printing_mm_parameters_layout.addWidget(self.single_material_mode_checkbox, 0, 1, 1, 3)
        #printing_mm_parameters_layout.addWidget(self.single_material_mode_l, 0, 2, 1, 2)

        printing_mm_parameters_layout.addWidget(self.materials_settings_l, 1, 0, 1, 3)

        printing_mm_parameters_layout.addWidget(self.extruder1_cb, 2, 0)
        printing_mm_parameters_layout.addWidget(self.extruder1_l, 2, 1)
        printing_mm_parameters_layout.addWidget(self.extruder1_c, 2, 2, 1, 2)

        printing_mm_parameters_layout.addWidget(self.extruder2_cb, 3, 0)
        printing_mm_parameters_layout.addWidget(self.extruder2_l, 3, 1)
        printing_mm_parameters_layout.addWidget(self.extruder2_c, 3, 2, 1, 2)

        printing_mm_parameters_layout.addWidget(self.extruder3_cb, 4, 0)
        printing_mm_parameters_layout.addWidget(self.extruder3_l, 4, 1)
        printing_mm_parameters_layout.addWidget(self.extruder3_c, 4, 2, 1, 2)

        printing_mm_parameters_layout.addWidget(self.extruder4_cb, 5, 0)
        printing_mm_parameters_layout.addWidget(self.extruder4_l, 5, 1)
        printing_mm_parameters_layout.addWidget(self.extruder4_c, 5, 2, 1, 2)

        #add size of wipe tower combobox
        printing_mm_parameters_layout.addWidget(self.wipe_tower_l, 6, 1)
        printing_mm_parameters_layout.addWidget(self.wipe_tower_c, 6, 2, 1, 2)




        printing_parameters_layout.addWidget(self.printer_settings_l, 6, 0, 1, 3)
        printing_parameters_layout.addWidget(self.materialLabel, 7,0)
        printing_parameters_layout.addWidget(self.materialCombo, 7, 1, 1, 3)
        printing_parameters_layout.addWidget(self.qualityLabel, 8, 0)
        printing_parameters_layout.addWidget(self.qualityCombo, 8, 1, 1, 3)
        printing_parameters_layout.addWidget(self.infillLabel, 9, 0)
        #printing_parameters_layout.addWidget(self.infillSlider, 3, 1, 1, 3)
        printing_parameters_layout.addWidget(self.infillCombo, 9, 1, 1, 3)
        printing_parameters_layout.addWidget(self.supportLabel, 10, 0)
        printing_parameters_layout.addWidget(self.supportCombo, 10, 1, 1, 3)
        printing_parameters_layout.addWidget(self.brim_label, 11, 0)
        printing_parameters_layout.addWidget(self.brimCheckBox, 11, 1, 1, 3)

        self.right_panel_layout.addLayout(printing_mm_parameters_layout)
        self.right_panel_layout.addLayout(printing_parameters_layout)

        self.right_panel_layout.addWidget(self.object_group_box)
        self.right_panel_layout.addWidget(self.object_variable_layer_box)
        self.right_panel_layout.addWidget(self.gcode_group_box)
        self.right_panel_layout.addStretch()
        #self.right_panel_layout.addItem(QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding))

        self.right_panel_layout.addWidget(self.generateButton)
        self.right_panel_layout.addWidget(self.saveBW)
        self.right_panel_layout.addWidget(self.progressBar)
        self.right_panel_layout.addWidget(self.gcode_back_b)
        self.right_panel_layout.addSpacerItem(QSpacerItem(0, 5, QSizePolicy.Minimum, QSizePolicy.Minimum))

        self.right_panel.setLayout(self.right_panel_layout)


        if self.controller.app_config.system_platform in ['Windows', 'Linux']:
            printing_parameters_layout.setColumnMinimumWidth(1, (int)(100 * self.controller.dpi_coef))
            self.right_panel.setFixedWidth((int)(250 * self.controller.dpi_coef))
        else:
            printing_parameters_layout.setColumnMinimumWidth(1, 150)
            self.right_panel.setFixedWidth((int) (300*self.controller.dpi_coef))


        #self.right_panel.setMinimumWidth((int)(250*self.controller.dpi_coef))
        #self.right_panel.setMaximumWidth((int)(275*self.controller.dpi_coef))

        print("Sirka praveho panelu: " + str(self.right_panel.width()))
        self.transformation_reset_b.move((int)(self.right_panel.width() - 27*self.controller.dpi_coef), 13)
        self.gcode_help_b.move((int)(self.right_panel.width() - 27*self.controller.dpi_coef), 13)

        #print("create gcode panel")
        self.gcode_panel = QWidget()
        self.gcode_label = QLabel("0")
        self.gcode_label.setMaximumWidth((int)(40*self.controller.dpi_coef))
        self.gcode_label.setAlignment(Qt.AlignCenter)

        mainLayout = QHBoxLayout()
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        #mainLayout.setContentsMargin(0, 0, 0, 0)
        #mainLayout.setMargin(0)
        #mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.addWidget(self.glWidget)
        mainLayout.addWidget(self.scroll_area)
        #mainLayout.addWidget(self.right_panel)
        self.scroll_area.setWidget(self.right_panel)
        self.scroll_area.setAutoFillBackground(True)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedWidth(self.right_panel.width())
        self.scroll_area.show()

        self.centralWidget.setLayout(mainLayout)
        self.setCentralWidget(self.centralWidget)

        #self.statusBar().showMessage('Ready')
        self.setWindowTitle("PrusaControl " + self.controller.app_config.version)
        #print("Set window title")

        #print("Retranslate UI")
        self.retranslateUI()

        self.setVisible(True)

        #self.changable_widgets['brimCheckBox'] = self.brimCheckBox
        #self.changable_widgets['supportCheckBox'] = self.supportCheckBox
        #self.changable_widgets['supportCombo'] = self.supportCombo


        self.qualityCombo.currentIndexChanged.connect(self.controller.scene_was_changed)
        #self.infillSlider.valueChanged.connect(self.controller.scene_was_changed)
        #self.supportCheckBox.clicked.connect(self.controller.scene_was_changed)
        #self.supportCombo.currentIndexChanged.connect(self.controller.scene_was_changed)
        self.supportCombo.currentIndexChanged.connect(self.controller.actualize_extruders)
        self.brimCheckBox.clicked.connect(self.controller.scene_was_changed)

        #print("created all widgets")
        self.glWidget.setFocusPolicy(Qt.StrongFocus)
        #print("set strong focus for GL")

        #self.set_scale(self.controller.dpi_coef)

        #print("Show all")
        self.show()

    def get_list_of_wipe_tower_labels(self):
        return [self.tr("Reduced"), self.tr("Normal"), self.tr("Increased/Soluble")]

    def change_of_wipe_tower_settings(self):
        index = self.wipe_tower_c.currentIndex()
        self.controller.change_of_wipe_tower_settings(index)

    def update_object_extruders_cb(self):
        actual_index = self.object_extruder_c.currentIndex()
        self.object_extruder_c.clear()

        model = self.object_extruder_c.model()
        for n, i in enumerate(['Extruder 1', 'Extruder 2', 'Extruder 3', 'Extruder 4']):
            item = QStandardItem(str(i))
            item.setBackground(self.controller.get_extruder_color(n+1))
            model.appendRow(item)

        self.object_extruder_c.setCurrentIndex(actual_index)


    def set_scale(self, scale):
        #resize window
        #self.setFixedSize((int)(scale * self.maximumWidth()), (int)(scale * self.maximumHeight()))
        #resize layouts with widgets
        for widget in self.centralWidget.children():
            if not type(widget) is QHBoxLayout and \
                not type(widget) is QPropertyAnimation and \
                not type(widget) is sceneRender.GLWidget:
                #print(str(type(widget)))
                #print(scale* widget.maximumWidth())
                #print(scale * widget.maximumHeight())
                widget.setFixedSize((int)(scale * widget.maximumWidth()), (int)(scale * widget.maximumHeight()))

    def update_actions_in_menu(self):
        self.saveMenu.clear()
        self.saveMenu.addActions(self.get_actual_action_list(self.saveButton))


    def get_actual_action_list(self, button_widget):
        actionList = []

        action = QAction(self.tr("Save G-Code"), self)
        action.triggered.connect(self.controller.generate_button_pressed)
        actionList.append(action)

        for address in self.controller.list_of_printing_services:
            action_tmp = QAction("Print on %s" % address, self)
            action_tmp.triggered.connect(self.make_action)
            actionList.append(action_tmp)

        action_tmp = QAction("Add OctoPrint", self)
        action_tmp.triggered.connect(self.controller.add_new_octoprint)
        actionList.append(action_tmp)

        return actionList

    def make_action(self):
        sender = self.sender()
        self.saveButton.setText(sender.text())
        self.controller.set_print_on(sender.text())


    def open_color_pick_dialog1(self):
        color = QColorDialog.getColor(self.extruder1_color)
        if color.isValid():
            self.extruder1_color = color
            self.extruder1_cb.setStyleSheet("background-color: rgb(%s, %s, %s)" % (color.red(), color.green(), color.blue()))
            self.update_object_extruders_cb()

    def open_color_pick_dialog2(self):
        color = QColorDialog.getColor(self.extruder2_color)
        if color.isValid():
            self.extruder2_color = color
            self.extruder2_cb.setStyleSheet("background-color: rgb(%s, %s, %s)" % (color.red(), color.green(), color.blue()))
            self.update_object_extruders_cb()

    def open_color_pick_dialog3(self):
        color = QColorDialog.getColor(self.extruder3_color)
        if color.isValid():
            self.extruder3_color = color
            self.extruder3_cb.setStyleSheet("background-color: rgb(%s, %s, %s)" % (color.red(), color.green(), color.blue()))
            self.update_object_extruders_cb()

    def open_color_pick_dialog4(self):
        color = QColorDialog.getColor(self.extruder4_color)
        if color.isValid():
            self.extruder4_color = color
            self.extruder4_cb.setStyleSheet("background-color: rgb(%s, %s, %s)" % (color.red(), color.green(), color.blue()))
            self.update_object_extruders_cb()


    def set_default(self):
        _, first = self.controller.get_printer_materials_labels_ls(self.controller.get_actual_printer())
        self.materialCombo.setCurrentIndex(first)

        self.extruder1_c.setCurrentIndex(first)
        self.extruder2_c.setCurrentIndex(first)
        self.extruder3_c.setCurrentIndex(first)
        self.extruder4_c.setCurrentIndex(first)

        self.brimCheckBox.setChecked(False)
        self.supportCombo.setCurrentIndex(0)


    def retranslateUI(self):
        self.name_l.setText(self.tr("Name"))
        self.object_extruder_l.setText(self.tr("Extruder"))
        self.position_l.setText(self.tr("Position"))
        self.rotation_l.setText(self.tr("Rotation"))
        self.scale_l.setText(self.tr("Scale"))

        self.combobox_scale_units.setToolTip(self.tr("In what units you want to scale?"))

        self.lock_scale_axes_l.setText(self.tr("Lock axes"))
        self.lock_scale_axes_checkbox.setToolTip(self.tr("Lock of scaling axis"))

        self.place_on_zero_l.setText(self.tr("Place on bed"))
        self.place_on_zero.setToolTip(self.tr("Automatic placing of models\n on printing bed in Z axis"))

        self.units_l.setText(self.tr('Units'))

        self.advance_settings_b.setText(self.tr("Advance Settings"))
        self.basic_settings_b.setText(self.tr("Basic Settings"))

        self.color_change_l.setText(self.tr("And color change"))
        self.gcode_back_b.setText(self.tr("Back"))

        self.printer_settings_l.setText(self.tr("Printer settings"))

        self.materialLabel.setText(self.tr("Material"))
        self.material_tooltip = self.tr("Select material for printing")
        self.materialLabel.setToolTip(self.material_tooltip)
        self.materialCombo.setToolTip(self.material_tooltip)


        self.qualityLabel.setText(self.tr("Quality"))
        self.quality_tooltip = self.tr("Select quality for printing")
        self.qualityLabel.setToolTip(self.quality_tooltip)
        self.qualityCombo.setToolTip(self.quality_tooltip)

        self.infillLabel.setText(self.tr("Infill"))
        self.infill_tooltip = self.tr("Select how much space inside of model have to be filled")
        self.infillLabel.setToolTip(self.infill_tooltip)
        self.infillCombo.setToolTip(self.infill_tooltip)

        self.supportLabel.setText(self.tr("Support"))
        self.support_tooltip = self.tr("Select what kind of supports do you need, if any")
        self.supportCombo.clear()
        self.set_normal_support_settings()
        self.supportLabel.setToolTip(self.support_tooltip)
        self.supportCombo.setToolTip(self.support_tooltip)

        self.brim_tooltip = self.tr("Do you need better adhesive of model and printing bed?")
        self.brim_label.setText(self.tr("Brim"))
        self.brim_label.setToolTip(self.brim_tooltip)
        self.brimCheckBox.setToolTip(self.brim_tooltip)

        self.single_material_mode_tooltip = self.tr("Do you want to print only from one material?")
        self.single_material_mode_checkbox.setText(self.tr("Single material mode"))
        self.materials_settings_l.setText(self.tr("Material Settings"))
        self.extruder1_l.setText(self.tr("Extruder 1"))
        self.extruder2_l.setText(self.tr("Extruder 2"))
        self.extruder3_l.setText(self.tr("Extruder 3"))
        self.extruder4_l.setText(self.tr("Extruder 4"))
        self.wipe_tower_tooltip = self.tr("Amount of material in wipe tower, material clearing")
        self.wipe_tower_l.setText(self.tr("Wipe amount"))
        self.wipe_tower_c.setToolTip(self.wipe_tower_tooltip)
        self.wipe_tower_l.setToolTip(self.wipe_tower_tooltip)

        self.used_extruder_tooltip = self.tr("Extruder is used")


        self.object_group_box.setTitle(self.tr("Object settings"))
        self.object_variable_layer_box.setTitle(self.tr("Object advance settings"))
        self.gcode_group_box.setTitle(self.tr("Gcode preview"))

        self.transformation_reset_b.setToolTip(self.tr("Reset transformations"))

        self.generateButton.setText(self.tr("Generate"))
        self.generateButton.setToolTip(self.tr("Generate scene with actual options to gcode file"))

        self.create_menu()

        self.controller.create_messages()


    def set_special_support_settings(self):
        item_lst = [[self.tr("None"), self.tr("None")],
                    [self.tr("Build plate only, soluble"), self.tr("Build plate only, soluble")],
                    [self.tr("Everywhere, soluble"), self.tr("Everywhere, soluble")],
                    [self.tr("Build plate only, soluble interface"), self.tr("Build plate only with soluble interface")],
                    [self.tr("Everywhere, soluble interface"), self.tr("Everywhere with soluble interface")]]

        print("GUI set special support settings")
        self.supportCombo.clear()
        for i in item_lst:
            self.supportCombo.addItem(i[0], i[1])


    def set_normal_support_settings(self):
        print("GUI set normal support settings")
        self.supportCombo.clear()
        self.supportCombo.addItems([self.tr("None"), self.tr("Build plate only"), self.tr("Everywhere")])

    def set_multimaterial_gui_on(self, apply_on_single_mode_switch=False):
        self.create_menu()

        if apply_on_single_mode_switch:
            self.single_material_mode_checkbox.setVisible(True)
            self.single_material_mode_checkbox.setChecked(False)

        self.materials_settings_l.setVisible(True)


        self.extruder1_cb.setVisible(True)
        self.extruder1_l.setVisible(True)
        self.extruder1_c.setVisible(True)
        self.extruder2_cb.setVisible(True)
        self.extruder2_l.setVisible(True)
        self.extruder2_c.setVisible(True)

        self.extruder3_cb.setVisible(True)
        self.extruder3_l.setVisible(True)
        self.extruder3_c.setVisible(True)
        self.extruder4_cb.setVisible(True)
        self.extruder4_l.setVisible(True)
        self.extruder4_c.setVisible(True)

        self.wipe_tower_l.setVisible(True)
        self.wipe_tower_c.setVisible(True)

        self.object_extruder_l.setVisible(True)
        self.object_extruder_c.setVisible(True)

        self.materialCombo.setVisible(False)
        self.materialLabel.setVisible(False)

        self.color_change_l.setVisible(False)



    def set_multimaterial_gui_off(self, apply_on_single_mode_switch=False):
        self.create_menu()

        if apply_on_single_mode_switch:
            self.single_material_mode_checkbox.setVisible(False)

        #self.printing_mm_parameters_layout

        self.materials_settings_l.setVisible(False)
        self.extruder1_cb.setVisible(False)
        self.extruder1_l.setVisible(False)
        self.extruder1_c.setVisible(False)

        self.extruder2_cb.setVisible(False)
        self.extruder2_l.setVisible(False)
        self.extruder2_c.setVisible(False)

        self.extruder3_cb.setVisible(False)
        self.extruder3_l.setVisible(False)
        self.extruder3_c.setVisible(False)

        self.extruder4_cb.setVisible(False)
        self.extruder4_l.setVisible(False)
        self.extruder4_c.setVisible(False)

        self.wipe_tower_l.setVisible(False)
        self.wipe_tower_c.setVisible(False)

        self.object_extruder_l.setVisible(False)
        self.object_extruder_c.setVisible(False)

        self.materialCombo.setVisible(True)
        self.materialLabel.setVisible(True)

        self.color_change_l.setVisible(True)

        self.set_normal_support_settings()


    def create_menu(self):
        self.menubar.clear()
        # file menu definition
        self.file_menu = self.menubar.addMenu(self.tr('&File'))
        self.file_menu.addAction(self.tr('Import model file'), self.controller.open_model_file)
        self.file_menu.addAction(self.tr('Import multipart model file'), self.controller.open_multipart_model)
        self.file_menu.addAction(self.tr('Import gcode file'), self.controller.open_gcode_file)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.tr('Open project'), self.controller.open_project_file)
        self.file_menu.addAction(self.tr('Save project'), self.controller.save_project_file)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.tr('Reset'), self.controller.reset)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.tr('Close'), self.controller.close)
        # file menu definition

        # edit menu definition
        self.edit_menu = self.menubar.addMenu(self.tr('&Edit'))
        self.edit_menu.addAction(self.tr('Undo') + '\tCtrl+Z', self.controller.undo_function)
        self.edit_menu.addAction(self.tr('Redo') + '\tCtrl+Y', self.controller.do_function)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.tr('Copy') +'\tCtrl+C', self.controller.copy_selected_objects)
        self.edit_menu.addAction(self.tr('Paste') + '\tCtrl+V', self.controller.paste_selected_objects)
        self.edit_menu.addAction(self.tr('Delete') + '\tDel', self.controller.delete_selected_objects)
        # self.edit_menu.addSeparator()
        # self.edit_menu.addAction(self.tr('Info'), self.controller.close)
        # edit menu definition

        # TODO:Uncoment after new function created/tested
        # printer menu
        # self.printer_menu = self.menubar.addMenu(self.tr('&Printer'))
        # self.printer_menu.addAction(self.tr('Printer info'), self.controller.open_printer_info)
        # self.printer_menu.addAction(self.tr('Update firmware'), self.controller.open_update_firmware)
        # printer menu

        # Settings menu
        self.settings_menu = self.menubar.addMenu(self.tr('&Settings'))
        self.settings_menu.addAction(self.tr('PrusaControl settings'), self.controller.open_settings)
        # Settings menu

        # Help menu
        self.help_menu = self.menubar.addMenu(self.tr('&Help'))
        self.help_menu.addAction(self.tr('Help'), self.controller.open_help)
        self.help_menu.addAction(self.tr('Prusa Online'), self.controller.open_shop)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.tr("Send feedback"), self.controller.send_feedback)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.tr('About'), self.controller.open_about)
        # Help menu

    def reset_transformation_on_object(self, object_id):
        self.controller.reset_transformation_on_object(object_id)
        mesh = self.controller.get_object_by_id(object_id)
        if mesh.is_wipe_tower:
            self.update_position_widgets(object_id)
        else:
            self.update_position_widgets(object_id)
            self.update_rotate_widgets(object_id)
            self.update_scale_widgets(object_id)
        self.update_scene()

    def show_new_version_message(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("New version"))
        msgBox.setText(self.tr("New version is out!"))
        msgBox.setInformativeText(self.tr("Do you want to download new version?"))
        msgBox.setStandardButtons(QMessageBox.Yes |  QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))
        msgBox.setDefaultButton(QMessageBox.Yes)

        return msgBox.exec_()


    def show_exit_message_scene_not_saved(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("Save"))
        msgBox.setText(self.tr("Scene is not saved."))
        msgBox.setInformativeText(self.tr("Do you want to save your changes?"))
        msgBox.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        msgBox.setDefaultButton(QMessageBox.Save)
        msgBox.button(msgBox.Save).setText(self.tr("Save"))
        msgBox.button(msgBox.Discard).setText(self.tr("Discard"))
        msgBox.button(msgBox.Cancel).setText(self.tr("Cancel"))


        return msgBox.exec_()


    def show_exit_message_generating_scene(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("Exit"))
        msgBox.setText(self.tr("GCode is in generating process."))
        msgBox.setInformativeText(self.tr("Do you want to cancel generating of GCode and exit?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))

        return msgBox.exec_()

    def show_cancel_generating_dialog_and_load_file(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("Load file"))
        msgBox.setText(self.tr("GCode is in generating process."))
        msgBox.setInformativeText(self.tr("Do you want to cancel generating of GCode and load file?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))

        return msgBox.exec_()

    def show_ask_multipart_model_dialog(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("Load file"))
        msgBox.setText(self.tr("List of Stl files"))
        msgBox.setInformativeText(self.tr("Do you want to load multiple stl files as one multipart object?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))

        return msgBox.exec_()

    def show_cancel_generating_dialog_and_load_file(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("Load file"))
        msgBox.setText(self.tr("GCode file is in loading process."))
        msgBox.setInformativeText(self.tr("Do you want to cancel loading of GCode file and load this file?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))

        return msgBox.exec_()

    def show_clear_scene_and_load_gcode_file_dialog(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("Scene not empty"))
        msgBox.setText(self.tr("Some objects are in scene"))
        msgBox.setInformativeText(self.tr("Do you want to clear scene and load GCode file?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))

        return msgBox.exec_()

    def show_open_cancel_gcode_preview_dialog(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("GCode is generated"))
        msgBox.setText(self.tr("Scene is generated to GCode"))
        msgBox.setInformativeText(self.tr("Do you want to close GCode preview and import new file?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))

        return msgBox.exec_()

    def show_open_new_octoprint_dialog(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("GCode is generated"))
        msgBox.setText(self.tr("Scene is generated to GCode"))
        msgBox.setInformativeText(self.tr("Do you want to close GCode preview and import new file?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(msgBox.Yes).setText(self.tr("Yes"))
        msgBox.button(msgBox.No).setText(self.tr("No"))

        return msgBox.exec_()

    def open_project_asking_dialog(self):
        msgBox = QMessageBox(self)
        msgBox.setObjectName("msgBox")
        msgBox.setWindowTitle(self.tr("Open project file"))
        msgBox.setText(self.tr("In scene are some objects"))
        msgBox.setInformativeText(self.tr("Do you want to open project file and clear actual scene?"))
        butt_open = msgBox.addButton(self.tr("Open"), QMessageBox.YesRole)
        butt_insert = msgBox.addButton(self.tr("Insert"), QMessageBox.YesRole)
        msgBox.addButton(QMessageBox.Cancel)
        msgBox.setDefaultButton(butt_open)
        ret = msgBox.exec_()

        if msgBox.clickedButton() == butt_open:
            return "Open"
        elif ret == QMessageBox.Cancel:
            return False
        elif msgBox.clickedButton() == butt_insert:
            return "Insert"

        return False


    def place_on_zero_changed(self):
        if self.place_on_zero.isChecked():
            self.edit_pos_z.setDisabled(True)
            model = self.controller.get_object_by_id(self.object_id)
            if model.is_multipart_model:
                model.multipart_parent.place_on_zero()
            else:
                model.place_on_zero()
            self.update_position_widgets(self.object_id)
            self.update_scene()
        else:
            self.edit_pos_z.setDisabled(False)


    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseMove:
            if event.buttons() == Qt.NoButton and isinstance(source, sceneRender.GLWidget):
                if self.controller.settings['toolButtons']['rotateButton'] or\
                        self.controller.settings['toolButtons']['scaleButton']:

                    self.controller.select_tool_helper(event)
                    self.update_scene()

        if event.type() == QEvent.MouseButtonPress:
            if (event.buttons() == Qt.LeftButton or event.buttons() == Qt.RightButton) and self.controller.show_gcode_help():
                self.controller.set_gcode_help_button_released()

        return QMainWindow.eventFilter(self, source, event)


    def closeEvent(self, event):
        if self.controller.exit_event():
        #if self.exit_message_continue_exitting():
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            QMainWindow.closeEvent(self, event)
        else:
            event.ignore()


    def reinit(self):
        self.set_default()
        self.update_gui_for_material()
        self.gcode_slider.init_points()

    def set_progress_bar(self, value):
        self.progressBar.setValue(value)
        #self.progressBar.setAlignment(Qt.AlignCenter)

    def set_save_gcode_button(self):
        self.saveBW.setVisible(True)

        self.generateButton.setVisible(False)
        self.generateButton.setText(self.tr("Save G-Code"))
        self.generateButton.setToolTip(self.tr("Save generated gcode file"))

    def set_cancel_button(self):
        self.generateButton.setText(self.tr("Cancel"))
        self.generateButton.setToolTip(self.tr("Cancel of generating gcode file"))

    def set_cancel_saving_gcode_button(self):
        self.generateButton.setText(self.tr("Cancel"))
        self.generateButton.setToolTip(self.tr("Cancel of saving gcode file"))

    def set_generate_button(self):
        self.generateButton.setText(self.tr("Generate"))
        self.generateButton.setToolTip(self.tr("Generate scene with actual options to gcode file"))

    def set_cancel_of_loading_gcode_file(self):
        self.generateButton.setEnabled(True)
        self.generateButton.setText(self.tr("Cancel file read"))
        self.generateButton.setToolTip(self.tr("Cancel of reading file"))

    def set_print_info_text(self, string):
        self.printing_filament_data.setText(string)

    def get_changable_widgets(self):
        return self.changable_widgets

    def get_object_id(self):
        return self.object_id

    def enable_editing(self):
        self.single_material_mode_checkbox.setEnabled(True)
        self.materials_settings_l.setEnabled(True)
        self.extruder1_l.setEnabled(True)
        self.extruder1_cb.setEnabled(True)
        self.extruder1_c.setEnabled(True)
        self.extruder2_l.setEnabled(True)
        self.extruder2_cb.setEnabled(True)
        self.extruder2_c.setEnabled(True)
        self.extruder3_l.setEnabled(True)
        self.extruder3_cb.setEnabled(True)
        self.extruder3_c.setEnabled(True)
        self.extruder4_l.setEnabled(True)
        self.extruder4_cb.setEnabled(True)
        self.extruder4_c.setEnabled(True)

        self.wipe_tower_l.setEnabled(True)
        self.wipe_tower_c.setEnabled(True)

        self.materialCombo.setEnabled(True)
        self.qualityCombo.setEnabled(True)
        self.infillCombo.setEnabled(True)
        self.supportCombo.setEnabled(True)
        self.brimCheckBox.setEnabled(True)

        self.printer_settings_l.setEnabled(True)
        self.materialLabel.setEnabled(True)
        self.qualityLabel.setEnabled(True)
        self.infillLabel.setEnabled(True)
        self.supportLabel.setEnabled(True)
        self.brim_label.setEnabled(True)

        for a in self.file_menu.actions() + self.edit_menu.actions() + self.settings_menu.actions():
            a.setEnabled(True)


    def disable_editing(self):
        self.single_material_mode_checkbox.setEnabled(False)
        self.materials_settings_l.setEnabled(False)
        self.extruder1_l.setEnabled(False)
        self.extruder1_cb.setEnabled(False)
        self.extruder1_c.setEnabled(False)
        self.extruder2_l.setEnabled(False)
        self.extruder2_cb.setEnabled(False)
        self.extruder2_c.setEnabled(False)
        self.extruder3_l.setEnabled(False)
        self.extruder3_cb.setEnabled(False)
        self.extruder3_c.setEnabled(False)
        self.extruder4_l.setEnabled(False)
        self.extruder4_cb.setEnabled(False)
        self.extruder4_c.setEnabled(False)

        self.wipe_tower_l.setEnabled(False)
        self.wipe_tower_c.setEnabled(False)

        self.materialCombo.setEnabled(False)
        self.qualityCombo.setEnabled(False)
        self.infillCombo.setEnabled(False)
        self.supportCombo.setEnabled(False)
        self.brimCheckBox.setEnabled(False)

        self.printer_settings_l.setEnabled(False)
        self.materialLabel.setEnabled(False)
        self.qualityLabel.setEnabled(False)
        self.infillLabel.setEnabled(False)
        self.supportLabel.setEnabled(False)
        self.brim_label.setEnabled(False)

        for a in self.file_menu.actions() + self.edit_menu.actions() + self.settings_menu.actions():
            a.setEnabled(False)


    def update_position_widgets(self, object_id):
        mesh_tmp = self.controller.get_object_by_id(object_id)
        if not mesh_tmp:
            return
        if mesh_tmp.is_multipart_model:
            mesh = mesh_tmp.multipart_parent
        else:
            mesh = mesh_tmp
        self.object_id = object_id

        self.edit_pos_x.setDisabled(True)
        self.edit_pos_x.setValue(mesh.pos[0] * 10)
        self.edit_pos_x.setDisabled(False)

        self.edit_pos_y.setDisabled(True)
        self.edit_pos_y.setValue(mesh.pos[1] * 10)
        self.edit_pos_y.setDisabled(False)

        self.edit_pos_z.setDisabled(True)
        self.edit_pos_z.setValue(mesh.pos[2] * 10)
        if self.place_on_zero.isChecked():
            self.edit_pos_z.setDisabled(True)
        else:
            self.edit_pos_z.setDisabled(False)


    def update_rotate_widgets(self, object_id):
        mesh_tmp = self.controller.get_object_by_id(object_id)
        if not mesh_tmp:
            return
        if mesh_tmp.is_multipart_model:
            mesh = mesh_tmp.multipart_parent
        else:
            mesh = mesh_tmp
        self.object_id = object_id
        self.edit_rot_x.setDisabled(True)
        self.edit_rot_x.setValue(np.rad2deg(mesh.rot[0]))
        self.edit_rot_x.setDisabled(False)

        self.edit_rot_y.setDisabled(True)
        self.edit_rot_y.setValue(np.rad2deg(mesh.rot[1]))
        self.edit_rot_y.setDisabled(False)

        self.edit_rot_z.setDisabled(True)
        self.edit_rot_z.setValue(np.rad2deg(mesh.rot[2]))
        self.edit_rot_z.setDisabled(False)


    def update_scale_widgets(self, object_id):
        mesh_tmp = self.controller.get_object_by_id(object_id)
        if not mesh_tmp:
            return
        if mesh_tmp.is_multipart_model:
            mesh = mesh_tmp.multipart_parent
        else:
            mesh = mesh_tmp
        self.object_id = object_id
        self.set_scale_widgets(mesh)


    def select_model_by_filename(self, filename):
        mesh_tmp = self.controller.get_object_by_id(self.object_id)
        if filename == mesh_tmp.filename:
            return

        if mesh_tmp.is_multipart_model:
            parent = mesh_tmp.multipart_parent
            parts_lst = [[m.filename, m.id] for m in parent.models]
            for model in parts_lst:
                if filename == model[0]:
                    self.controller.unselect_objects()
                    self.controller.select_object(model[1])
                    #self.set_gui_for_object(model[1])



    def update_object_settings(self, object_id):
        if self.is_setting_panel_opened:
            self.set_gui_for_object(object_id)
        else:
            return

    def create_object_settings_menu(self, object_id):
        if self.is_setting_panel_opened:
            self.set_gui_for_object(object_id)
        else:
            mesh = self.controller.get_object_by_id(object_id)
            if not mesh:
                return
            self.object_group_box.setEnabled(True)
            self.object_group_box.setHidden(False)
            self.set_gui_for_object(object_id)
            self.is_setting_panel_opened = True
        self.glWidget.setFocusPolicy(Qt.NoFocus)

    def set_gui_for_object(self, object_id, scale_units_perc=True):
        mesh_tmp = self.controller.get_object_by_id(object_id)
        extruder_index = 0
        models_names_lst = []

        if not mesh_tmp:
            return

        if mesh_tmp.is_multipart_model:
            mesh = mesh_tmp.multipart_parent

            self.object_settings_layout.addWidget(self.filename_c, 0, 1, 1, 2)
            self.filename_c.setVisible(True)
            self.filename_label.setVisible(False)

            mesh_tmp_filename = mesh_tmp.filename
            models_names_lst = [m.filename for m in mesh.models]

            self.filename_c.blockSignals(True)
            self.filename_c.clear()
            self.filename_c.addItems(models_names_lst)
            self.filename_c.setCurrentIndex(models_names_lst.index(mesh_tmp_filename))
            self.filename_c.blockSignals(False)

        else:
            mesh = mesh_tmp
            self.filename_c.setVisible(False)
            self.filename_label.setVisible(True)
            self.object_settings_layout.addWidget(self.filename_label, 0, 1, 1, 2)

        self.object_group_box.setEnabled(True)
        self.object_id = object_id

        if self.controller.is_multimaterial():
            extruder_index = mesh_tmp.extruder
            self.object_extruder_c.setCurrentIndex(extruder_index-1)

        self.filename_label.setText(mesh_tmp.filename)
        self.filename_label.setToolTip(mesh_tmp.filename)

        self.edit_pos_x.setDisabled(True)
        self.edit_pos_x.setValue(mesh.pos[0]*10)
        self.edit_pos_x.setDisabled(False)

        self.edit_pos_y.setDisabled(True)
        self.edit_pos_y.setValue(mesh.pos[1]*10)
        self.edit_pos_y.setDisabled(False)

        self.edit_pos_z.setDisabled(True)
        self.edit_pos_z.setValue(mesh.pos[2]*10)
        #default is disabled, after unticked of place_on_zero is enabled
        #self.edit_pos_z.setDisabled(False)

        self.edit_rot_x.setDisabled(True)
        self.edit_rot_x.setValue(np.rad2deg(mesh.rot[0]))
        self.edit_rot_x.setDisabled(False)

        self.edit_rot_y.setDisabled(True)
        self.edit_rot_y.setValue(np.rad2deg(mesh.rot[1]))
        self.edit_rot_y.setDisabled(False)

        self.edit_rot_z.setDisabled(True)
        self.edit_rot_z.setValue(np.rad2deg(mesh.rot[2]))
        self.edit_rot_z.setDisabled(False)

        self.set_scale_widgets(mesh)

        if mesh.is_wipe_tower:
            self.disable_edit_for_wipe_tower()
        else:
            self.enable_edit_for_normal_objects()

        self.variable_layer_widget.setMaximum(mesh.size[2]*10.)
        self.variable_layer_widget.setMinimum(0.0)
        self.variable_layer_widget.set_number_of_ticks(10)
        self.variable_layer_widget.set_model(mesh)

    def disable_edit_for_wipe_tower(self):
        self.edit_scale_x.setEnabled(False)
        self.edit_scale_y.setEnabled(False)
        self.edit_scale_z.setEnabled(False)
        self.combobox_scale_units.setEnabled(False)

        self.edit_rot_x.setEnabled(False)
        self.edit_rot_y.setEnabled(False)
        self.edit_rot_z.setEnabled(False)

        self.object_extruder_c.setEnabled(False)
        self.place_on_zero.setEnabled(False)
        self.lock_scale_axes_checkbox.setEnabled(False)

    def enable_edit_for_normal_objects(self):
        self.edit_scale_x.setEnabled(True)
        self.edit_scale_y.setEnabled(True)
        self.edit_scale_z.setEnabled(True)
        self.combobox_scale_units.setEnabled(True)

        self.edit_rot_x.setEnabled(True)
        self.edit_rot_y.setEnabled(True)
        self.edit_rot_z.setEnabled(True)

        self.object_extruder_c.setEnabled(True)
        self.place_on_zero.setEnabled(True)
        self.lock_scale_axes_checkbox.setEnabled(True)


    def set_scale_widgets(self, mesh):
        self.edit_scale_x.setDisabled(True)
        self.edit_scale_y.setDisabled(True)
        self.edit_scale_z.setDisabled(True)

        if self.scale_units == '%':
            self.edit_scale_x.setSuffix("%")
            self.edit_scale_x.setValue(mesh.scale[0] * 100)
            self.edit_scale_y.setSuffix("%")
            self.edit_scale_y.setValue(mesh.scale[1] * 100)
            self.edit_scale_z.setSuffix("%")
            self.edit_scale_z.setValue(mesh.scale[2] * 100)
        else:
            self.edit_scale_x.setSuffix("mm")
            self.edit_scale_x.setValue(mesh.scale[0] * mesh.size_origin[0] * 10)
            self.edit_scale_y.setSuffix("mm")
            self.edit_scale_y.setValue(mesh.scale[1] * mesh.size_origin[1] * 10)
            self.edit_scale_z.setSuffix("mm")
            self.edit_scale_z.setValue(mesh.scale[2] * mesh.size_origin[2] * 10)

        self.edit_scale_x.setDisabled(False)
        self.edit_scale_y.setDisabled(False)
        self.edit_scale_z.setDisabled(False)


    def change_scale_units(self):
        mesh_tmp = self.controller.get_object_by_id(self.object_id)
        if not mesh_tmp:
            return
        if mesh_tmp.is_multipart_model:
            mesh = mesh_tmp.multipart_parent
        else:
            mesh = mesh_tmp
        self.scale_units = self.combobox_scale_units.currentText()
        self.set_scale_widgets(mesh)

    def lock_scale_axes_change(self):
        self.lock_scale_axis = self.lock_scale_axes_checkbox.isChecked()
        #if self.lock_scale_axis:
            #self.scale_ration = [1.,.5,.5]

    def clear_object_settings_panel(self):
        self.filename_label.setText("")

        self.edit_pos_x.setValue(0.0)
        self.edit_pos_y.setValue(0.0)
        self.edit_pos_z.setValue(0.0)

        self.edit_rot_x.setValue(0)
        self.edit_rot_y.setValue(0)
        self.edit_rot_z.setValue(0)

        self.edit_scale_x.setValue(100)
        self.edit_scale_y.setValue(100)
        self.edit_scale_z.setValue(100)


    def close_object_settings_panel(self):
        self.is_setting_panel_opened = False
        self.filename_c.setVisible(False)
        self.filename_label.setVisible(True)
        self.object_settings_layout.addWidget(self.filename_label, 0, 1, 1, 2)

        self.object_group_box.setDisabled(True)
        self.clear_object_settings_panel()
        self.object_id = 0
        self.glWidget.setFocusPolicy(Qt.StrongFocus)

    def disable_object_settings_panel(self):
        self.clear_object_settings_panel()
        self.filename_c.setVisible(False)
        self.filename_label.setVisible(True)
        self.object_settings_layout.addWidget(self.filename_label, 0, 1, 1, 2)
        self.object_group_box.setDisabled(True)

    def set_extruder_on_object(self, widget, object_id):
        if widget.hasFocus():
            model = self.controller.get_object_by_id(object_id)
            if not model:
                return
            model.set_extruder(widget.currentIndex()+1)
            self.controller.show_warning_if_used_materials_are_not_compatible()
            self.controller.recalculate_wipe_tower()
            self.controller.actualize_extruder_set()

    def set_position_on_object(self, widget, object_id, x, y, z, place_on_zero):
        if widget.hasFocus():
            self.controller.scene_was_changed()
            model = self.controller.get_object_by_id(object_id)
            if not model:
                return
            model.set_move(np.array([x*.1, y*.1, z*.1]), False, place_on_zero)
            self.controller.update_scene()

    #@timing
    def set_rotation_on_object(self, widget, object_id, x, y, z, place_on_zero):
        if widget.hasFocus():
            self.controller.scene_was_changed()
            model = self.controller.get_object_by_id(object_id)
            if not model:
                return
            model.set_rot(np.deg2rad(x), np.deg2rad(y), np.deg2rad(z), False, True, place_on_zero)
            self.controller.update_wipe_tower()
            self.controller.update_scene()
            self.controller.make_analyze()

    def set_scale_on_object(self, widget, active_axis, object_id, x, y, z, place_on_zero):
        if widget.hasFocus():
            self.controller.scene_was_changed()
            model_tmp = self.controller.get_object_by_id(object_id)
            if not model_tmp:
                return
            if model_tmp.is_multipart_model:
                model = model_tmp.multipart_parent
            else:
                model = model_tmp

            if self.scale_units == '%':
                if self.lock_scale_axis:

                    if active_axis=='x':
                        x_recalc = x
                        x_ration = x/(model.scale[0]*100.)

                        y_recalc = (model.scale[1]*100.) * x_ration
                        self.edit_scale_y.setDisabled(True)
                        self.edit_scale_y.setValue(y_recalc)
                        self.edit_scale_y.setDisabled(False)
                        z_recalc = (model.scale[2]*100.) * x_ration
                        self.edit_scale_z.setDisabled(True)
                        self.edit_scale_z.setValue(z_recalc)
                        self.edit_scale_z.setDisabled(False)
                    elif active_axis=='y':
                        y_recalc = y
                        y_ration = y / (model.scale[1]*100.)

                        x_recalc = (model.scale[0]*100.) * y_ration
                        self.edit_scale_x.setDisabled(True)
                        self.edit_scale_x.setValue(x_recalc)
                        self.edit_scale_x.setDisabled(False)
                        z_recalc = (model.scale[2]*100.) * y_ration
                        self.edit_scale_z.setDisabled(True)
                        self.edit_scale_z.setValue(z_recalc)
                        self.edit_scale_z.setDisabled(False)
                    elif active_axis == 'z':
                        z_recalc = z
                        z_ration = z / (model.scale[2]*100.)

                        x_recalc = (model.scale[0]*100.) * z_ration
                        self.edit_scale_x.setDisabled(True)
                        self.edit_scale_x.setValue(x_recalc)
                        self.edit_scale_x.setDisabled(False)
                        y_recalc = (model.scale[1]*100.) * z_ration
                        self.edit_scale_y.setDisabled(True)
                        self.edit_scale_y.setValue(y_recalc)
                        self.edit_scale_y.setDisabled(False)
                else:
                    x_recalc = x
                    y_recalc = y
                    z_recalc = z

                model_tmp.set_scale_abs(x_recalc * .01, y_recalc * .01, z_recalc * .01)

            else:
                #mm
                if self.lock_scale_axis:
                    #x = (x/model.size_origin[0])*0.1
                    #y = (y/model.size_origin[1])*0.1
                    #z = (z/model.size_origin[2])*0.1
                    #print("Vstupni parametry pro mm: %s %s %s" % (str(x), str(y), str(z)))

                    if active_axis == 'x':
                        x_ration = x/model.size_origin[0]

                        self.edit_scale_y.setDisabled(True)
                        self.edit_scale_y.setValue(model.size_origin[1] * x_ration)
                        self.edit_scale_y.setDisabled(False)
                        self.edit_scale_z.setDisabled(True)
                        self.edit_scale_z.setValue(model.size_origin[2] * x_ration)
                        self.edit_scale_z.setDisabled(False)

                        x_recalc = x_ration
                        y_recalc = x_ration
                        z_recalc = x_ration

                    elif active_axis == 'y':
                        y_ration = y / model.size_origin[1]

                        self.edit_scale_x.setDisabled(True)
                        self.edit_scale_x.setValue(model.size_origin[0] * y_ration)
                        self.edit_scale_x.setDisabled(False)
                        self.edit_scale_z.setDisabled(True)
                        self.edit_scale_z.setValue(model.size_origin[2] * y_ration)
                        self.edit_scale_z.setDisabled(False)

                        y_recalc = y_ration
                        x_recalc = y_ration
                        z_recalc = y_ration

                    elif active_axis == 'z':
                        z_ration = z / model.size_origin[2]

                        self.edit_scale_x.setDisabled(True)
                        self.edit_scale_x.setValue(model.size_origin[0] * z_ration)
                        self.edit_scale_x.setDisabled(False)
                        self.edit_scale_y.setDisabled(True)
                        self.edit_scale_y.setValue(model.size_origin[1] * z_ration)
                        self.edit_scale_y.setDisabled(False)

                        z_recalc = z_ration
                        x_recalc = z_ration
                        y_recalc = z_ration


                    x_recalc *= .1
                    y_recalc *= .1
                    z_recalc *= .1

                    #print("Vystupni parametry pro mm: %s %s %s" % (str(x_recalc), str(y_recalc), str(z_recalc)))
                    model_tmp.set_scale_abs(x_recalc, y_recalc, z_recalc)
                else:
                    model_tmp.set_scale_abs((x/model.size_origin[0])*0.1, (y/model.size_origin[1])*.1, (z/model.size_origin[2])*.1)


            #model.update_min_max()
            self.controller.update_wipe_tower()
        #self.update_object_settings(self.object_id)
        self.controller.update_scene()


    def create_object_settings_layout(self):
        object_settings_layout = QGridLayout()
        object_settings_layout.setRowMinimumHeight(5, 10)
        object_settings_layout.setRowMinimumHeight(9, 10)
        object_settings_layout.setRowMinimumHeight(15, 10)
        object_settings_layout.setVerticalSpacing(2)


        object_settings_layout.addWidget(self.name_l, 0, 0)
        self.name_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.filename_label, 0, 1, 1, 2)
        self.filename_label.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.filename_c, 0, 2, 1, 1)
        self.filename_c.setFixedHeight((int)(22*self.controller.dpi_coef))

        self.object_extruder_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        self.object_extruder_c.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.object_extruder_l, 1, 0, 1, 1)
        object_settings_layout.addWidget(self.object_extruder_c, 1, 1, 1, 2)
        #1
        object_settings_layout.addWidget(self.position_l, 2, 0)
        self.position_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.x_pos_l, 2, 1)
        self.x_pos_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_pos_x, 2, 2)
        self.edit_pos_x.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.y_pos_l, 3, 1)
        self.y_pos_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_pos_y, 3, 2)
        self.edit_pos_y.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.z_pos_l, 4, 1)
        self.z_pos_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_pos_z, 4, 2)
        self.edit_pos_z.setFixedHeight((int)(22*self.controller.dpi_coef))
        self.edit_pos_z.setDisabled(True)
        #5
        object_settings_layout.addWidget(self.rotation_l, 6, 0)
        self.rotation_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.x_rot_l, 6, 1)
        self.x_rot_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_rot_x, 6, 2)
        self.edit_rot_x.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.y_rot_l, 7, 1)
        self.y_rot_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_rot_y, 7, 2)
        self.edit_rot_y.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.z_rot_l, 8, 1)
        self.z_rot_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_rot_z, 8, 2)
        self.edit_rot_z.setFixedHeight((int)(22*self.controller.dpi_coef))
        #9
        object_settings_layout.addWidget(self.scale_l, 10, 0)
        self.scale_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.x_scale_l, 10, 1)
        self.x_scale_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_scale_x, 10, 2)
        self.edit_scale_x.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.y_scale_l, 11, 1)
        self.y_scale_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_scale_y, 11, 2)
        self.edit_scale_y.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.z_scale_l, 12, 1)
        self.z_scale_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.edit_scale_z, 12, 2)
        self.edit_scale_z.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.lock_scale_axes_checkbox, 10, 1, 3, 1, Qt.AlignRight)
        self.lock_scale_axes_checkbox.setFixedHeight(51)
        object_settings_layout.addWidget(self.units_l, 13, 1)
        self.units_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.combobox_scale_units, 13, 2)
        self.combobox_scale_units.setFixedHeight((int)(22*self.controller.dpi_coef))
        #object_settings_layout.addWidget(self.lock_scale_axes_l, 13, 1)
        #self.lock_scale_axes_l.setFixedHeight(22)

        #14
        object_settings_layout.addWidget(self.place_on_zero_l, 15, 0, 1, 2)
        self.place_on_zero_l.setFixedHeight((int)(22*self.controller.dpi_coef))
        object_settings_layout.addWidget(self.place_on_zero, 15, 2)
        self.place_on_zero.setFixedHeight((int)(22*self.controller.dpi_coef))

        object_settings_layout.addWidget(self.advance_settings_b, 16, 0, 1, 3)

        return object_settings_layout

    def create_object_advance_settings_layout(self):
        object_variable_layer_layout = QGridLayout()
        object_variable_layer_layout.setRowMinimumHeight(0, (int)(350*self.controller.dpi_coef))

        object_variable_layer_layout.addWidget(self.variable_layer_widget, 0, 0, 3, 3)
        object_variable_layer_layout.addWidget(self.basic_settings_b, 4, 0, 1, 3)

        return object_variable_layer_layout


    def create_gcode_view_layout(self):

        gcode_view_layout = QGridLayout()
        gcode_view_layout.setRowMinimumHeight(3, (int)(350*self.controller.dpi_coef))
        gcode_view_layout.setRowStretch(1, 0)
        gcode_view_layout.setRowStretch(2, 0)
        gcode_view_layout.setRowStretch(3, 2)

        gcode_view_layout.addWidget(self.color_change_l, 1, 0)
        gcode_view_layout.addWidget(self.gcode_slider, 2, 0, 3, 3)
        #gcode_view_layout.addWidget(self.gcode_back_b, 4, 0, 1, 3)

        return gcode_view_layout

    def saving_gcode(self):
        self.set_cancel_saving_gcode_button()
        self.progressBar.setVisible(True)
        self.gcode_back_b.setVisible(False)

    def open_gcode_view(self):
        self.update_actions_in_menu()
        self.set_save_gcode_button()
        self.object_group_box.setVisible(False)
        self.gcode_group_box.setVisible(True)
        if self.controller.is_multimaterial() and not self.controller.is_single_material_mode():
            self.gcode_help_b.setVisible(False)
        else:
            self.gcode_help_b.setVisible(True)

        self.progressBar.setVisible(False)
        self.gcode_back_b.setVisible(True)
        self.controller.view.update_scene()
        self.gcode_slider.setTickInterval(0)

    #def set_gcode_slider(self, number_of_layers=0, maximal_value=0):
    #    self.gcode_slider.setTickInterval(0)

    def close_gcode_view(self):
        self.gcode_group_box.setVisible(False)
        self.gcode_back_b.setVisible(False)
        self.saveBW.setVisible(False)
        self.generateButton.setVisible(True)
        self.progressBar.setVisible(True)
        self.object_group_box.setVisible(True)
        self.progressBar.setValue(0)

        self.controller.view.update_scene()


    def open_new_octoprint_dialog(self):
        data, ok = NewOctoPrintDialog.get_settings_data(self.controller)
        return data, ok

    def open_settings_dialog(self, editable=True):
        data, ok = SettingsDialog.get_settings_data(self.controller, editable, self.parent())
        return data, ok

    def open_printer_info_dialog(self):
        PrinterInfoDialog.get_printer_info_dialog(self.controller, self.parent())

    def open_about_dialog(self):
        AboutDialog.get_about_dialog(self.controller, self.parent())

    def open_firmware_dialog(self):
        data, ok = FirmwareUpdateDialog.get_firmware_update(self.controller, self.parent())

    def disable_generate_button(self):
        self.generateButton.setDisabled(True)

    def enable_generate_button(self):
        self.generateButton.setDisabled(False)

    def open_project_file_dialog(self):
        filters = "Prusa (*.prusa *.PRUSA)"
        title = 'Open project file'
        open_at = self.settings.value("project_path", "")
        data = QFileDialog.getOpenFileName(None, title, open_at, filters)[0]
        if data:
            self.settings.setValue("project_path", QFileInfo(data).absolutePath())
        return data

    def open_gcode_file_dialog(self):
        filters = "GCODE (*.gcode *.GCODE *.Gcode)"
        title = "Import gcode file"
        open_at = self.settings.value("gcode_path", "")
        data = QFileDialog.getOpenFileName(None, title, open_at, filters)[0]
        if data:
            self.settings.setValue("gcode_path", QFileInfo(data).absolutePath())
        return data

    def open_model_file_dialog(self):
        filters = "STL (*.stl *.STL)"
        title = "Import model file"
        open_at = self.settings.value("model_path", "")
        data = QFileDialog.getOpenFileNames(None, title, open_at, filters)[0]
        if data:
            self.settings.setValue("model_path", QFileInfo(data[0]).absolutePath())
        filenames_list = []
        for path in data:
            filenames_list.append(self.convert_file_path_to_unicode(path))
        return filenames_list

    def save_project_file_dialog(self):
        filters = "Prusa (*.prusa *.PRUSA)"
        title = 'Save project file'
        open_at = self.settings.value("project_path", "")
        data = QFileDialog.getSaveFileName(None, title, open_at, filters)[0]
        if data:
            self.settings.setValue("project_path", QFileInfo(data).absolutePath())
        if data == '':
            return data

        return data

    def save_gcode_file_dialog(self, filename = "sliced_model"):
        filters = "gcode (*.gcode *.GCODE)"
        title = 'Save G-Code file'
        open_at = self.settings.value("gcode_path", "")
        filename_list = filename.split('/')
        open_at += '/' + filename_list[-1]
        data = QFileDialog.getSaveFileName(None, title, open_at, filters)[0]
        if data:
            self.settings.setValue("gcode_path", QFileInfo(data).absolutePath())
        return data

    #TODO:Move to controller class
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super(PrusaControlView, self).dragEnterEvent(event)

    def dragMoveEvent(self, event):
        super(PrusaControlView, self).dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = [url.toLocalFile() for url in event.mimeData().urls()]
            if len(urls) > 1:
                self.controller.open_files(urls)
            else:
                path = urls[0]
                self.statusBar().showMessage('Dropped file name is ' + path)
                self.controller.open_file(path)

            event.acceptProposedAction()
        else:
            super(PrusaControlView, self).dropEvent(event)

    def convert_file_path_to_unicode(self, path):
        converted_path = path
        return converted_path


    def update_material_settings(self):
        self.controller.update_mm_material_settings()


    def update_gui(self):
        self.controller.scene_was_changed()
        self.update_gui_for_material()

    def update_gui_for_material(self, set_materials=0):
        labels, first = self.controller.get_printer_materials_labels_ls(self.controller.get_actual_printer())
        #print("Labels of materials: " + str(labels))
        #if self.controller.is_multimaterial():


        if self.controller.is_multimaterial() and not self.controller.is_single_material_mode():
            if set_materials:
                self.extruder1_c.blockSignals(True)
                self.extruder1_c.clear()
                self.extruder2_c.blockSignals(True)
                self.extruder2_c.clear()
                self.extruder3_c.blockSignals(True)
                self.extruder3_c.clear()
                self.extruder4_c.blockSignals(True)
                self.extruder4_c.clear()

                self.extruder1_c.addItems(labels)
                self.extruder2_c.addItems(labels)
                self.extruder3_c.addItems(labels)
                self.extruder4_c.addItems(labels)

                self.extruder1_c.setCurrentIndex(first)
                self.extruder1_c.setMaxVisibleItems((len(labels)))
                self.extruder2_c.setCurrentIndex(first)
                self.extruder2_c.setMaxVisibleItems((len(labels)))
                self.extruder3_c.setCurrentIndex(first)
                self.extruder3_c.setMaxVisibleItems((len(labels)))
                self.extruder4_c.setCurrentIndex(first)
                self.extruder4_c.setMaxVisibleItems((len(labels)))

                self.extruder1_c.blockSignals(False)
                self.extruder2_c.blockSignals(False)
                self.extruder3_c.blockSignals(False)
                self.extruder4_c.blockSignals(False)

            self.wipe_tower_c.blockSignals(True)
            self.wipe_tower_c.clear()
            self.wipe_tower_c.addItems(self.get_list_of_wipe_tower_labels())
            self.wipe_tower_c.setCurrentIndex(1)
            self.wipe_tower_c.blockSignals(False)

            material_label = self.extruder1_c.currentText()

            material_printing_settings = self.controller.get_printing_settings_for_material_by_label(material_label)

            self.qualityCombo.clear()
            material_printing_settings_quality_ls, first = self.controller.get_printer_material_quality_labels_ls_by_material_label(material_label)
            self.qualityCombo.addItems(material_printing_settings_quality_ls)
            self.qualityCombo.setCurrentIndex(first)
            self.qualityCombo.setMaxVisibleItems(len(material_printing_settings_quality_ls))

            infill_value = str(material_printing_settings['infill']) + '%'
            infill_list, first_infill = self.controller.get_infill_ls_and_index_of_default(infill_value)
            self.infillCombo.setCurrentIndex(first_infill)

        else:
            if set_materials:
                self.materialCombo.blockSignals(True)
                self.materialCombo.clear()
                #labels, first = self.controller.get_printer_materials_labels_ls(self.controller.actual_printer)
                self.materialCombo.addItems(labels)
                self.materialCombo.setCurrentIndex(first)
                self.materialCombo.setMaxVisibleItems((len(labels)))
                self.materialCombo.blockSignals(False)

            # material_label = self.materialCombo.currentText()
            material_label = self.materialCombo.currentText()

            material_printing_settings = self.controller.get_printing_settings_for_material_by_label(material_label)
            #print(str(material_printing_settings))

            # update print quality widget
            self.qualityCombo.clear()
            material_printing_settings_quality_ls, first = self.controller.get_printer_material_quality_labels_ls_by_material_label(material_label)
            #print("Quality list: " + str(material_printing_settings_quality_ls))
            self.qualityCombo.addItems(material_printing_settings_quality_ls)
            self.qualityCombo.setCurrentIndex(first)
            self.qualityCombo.setMaxVisibleItems(len(material_printing_settings_quality_ls))

            # infill slider
            #self.infillSlider.setValue(material_printing_settings['infill'])
            #self.infillSlider.setMinimum(material_printing_settings['infillRange'][0])
            #self.infillSlider.setMaximum(material_printing_settings['infillRange'][1])

            #material_printing_settings_infill_ls, first = self.controller.get_printer_material_quality_labels_ls_by_material_label(material_label)


            infill_value = str(material_printing_settings['infill'])+'%'
            infill_list, first_infill = self.controller.get_infill_ls_and_index_of_default(infill_value)
            self.infillCombo.setCurrentIndex(first_infill)

    def get_actual_printing_data(self):
        material_names = []
        if self.controller.is_multimaterial() and not self.controller.is_single_material_mode():
            print("Multimat")
            material_labels = []
            material_labels.append(self.extruder1_c.currentText())
            material_labels.append(self.extruder2_c.currentText())
            material_labels.append(self.extruder3_c.currentText())
            material_labels.append(self.extruder4_c.currentText())


            for mat in material_labels:
                material_names.append(self.controller.get_material_name_by_material_label(mat))
        else:
            print("Singlemat")
            material_label = self.materialCombo.currentText()
            material_names = [self.controller.get_material_name_by_material_label(material_label)]

        quality_label = self.qualityCombo.currentText()
        quality_name = self.controller.get_material_quality_name_by_quality_label(material_names[0], quality_label)

        infill_index = self.infillCombo.currentIndex()
        infill_value_ls = self.controller.get_infill_values_ls()
        infill_value = infill_value_ls[infill_index]
        brim = self.brimCheckBox.isChecked()
        support = self.supportCombo.currentIndex()

        if self.controller.soluble_extruder == -1:
            support_material_extruder = 0
            support_material_interface_extruder = 0
        else:
            support_material_extruder = self.controller.soluble_extruder
            support_material_interface_extruder = self.controller.soluble_extruder

        data = {'material': material_names,
                'quality': quality_name,
                'infill': infill_value,
                'brim': brim,
                'support_on_off': support,
                'support_build_plate': support,
                'overhangs': support,
                #for multimaterial special settings(soluble supports)
                'support_material_extruder': [support_material_extruder, support],
                'support_material_interface_extruder' : support_material_interface_extruder
                }
        return data

    def get_support_option(self):
        return self.supportCombo.currentIndex()

    def add_camera_position(self, vec):
        self.glWidget.camera_target += vec

    def set_x_rotation(self, angle):
        self.glWidget.set_x_rotation(angle)

    def set_z_rotation(self, angle):
        self.glWidget.set_z_rotation(angle)

    def get_x_rotation(self):
        return self.glWidget.xRot

    def get_z_rotation(self):
        return self.glWidget.zRot

    def get_zoom(self):
        return self.glWidget.get_zoom()

    def set_zoom(self, diff):
        self.glWidget.set_zoom(diff)

    def get_cursor_position(self, event):
        return self.glWidget.get_cursor_position(event)

    def get_cursor_pixel_color(self, event):
        return self.glWidget.get_cursor_pixel_color(event)

    def get_camera_direction(self, event):
        return self.glWidget.get_camera_direction(event)

    def get_tool_buttons(self):
        return self.glWidget.tools

    def update_scene(self, reset=False):
        self.glWidget.update_scene(reset)

    def set_gcode_slider(self, val):
        self.controller.set_gcode_layer(val)
        self.gcode_label.setText(self.controller.gcode.data_keys[val])

    def set_variable_layer_slider(self, val):
        self.controller.set_variable_layer_cursor(self.variable_layer_widget.double_value)


    def set_infill(self, val):
        self.infillValue = val
        infill_value_str = "%2d" % val
        self.infillLabel.setText(self.tr("Infill") + " " + infill_value_str + "%")

    def create_slider(self, setterSlot, defaultValue=0, rangeMin=0, rangeMax=100, orientation=Qt.Horizontal, base_class=QSlider):
        if base_class == Gcode_slider:
            slider = base_class(orientation, self.controller)
        else:
            slider = base_class(orientation)

        slider.setRange(rangeMin, rangeMax)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setTickInterval(1)
        slider.setValue(defaultValue)
        slider.setTickPosition(QSlider.TicksRight)

        if base_class == Gcode_slider:
            #self.connect(slider.slider, SIGNAL("valueChanged(int)"), setterSlot)
            slider.slider.valueChanged.connect(setterSlot)
        else:
            #self.connect(slider, SIGNAL("valueChanged(int)"), setterSlot)
            slider.valueChanged.connect(setterSlot)
        return slider
