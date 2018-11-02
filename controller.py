# -*- coding: utf-8 -*-
#import json
import json
import logging

#import functools


import time
import webbrowser
#from pprint import pprint
from configparser import RawConfigParser
from pprint import pprint

from shutil import copyfile, Error

import numpy
#import pyrr
import urllib3
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QTranslator, Qt, QPoint
from PyQt5.QtWidgets import QApplication
from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo

import sceneData
from analyzer import Analyzer
from gcode import GCode
from gui import PrusaControlView, QMessageBox
from parameters import AppParameters, PrintingParameters
from projectFile import ProjectFile
from sceneData import AppScene, ModelTypeStl
#from sceneRender import GLWidget
from copy import deepcopy

from itertools import compress


#import xml.etree.cElementTree as ET
#from zipfile import ZipFile

#from PyQt4 import QtCore, QtGui

#Mesure
from slicer import SlicerEngineManager

__author__ = 'Tibor Vavra'

def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        logging.debug('%s function took %0.3f ms' % (f.func_name, (time2-time1)*1000.0))
        return ret
    return wrap


class MyListener(object):

    def __init__(self, controller):
        pass
        self.controller = controller

    def remove_service(self, zeroconf, type, name):
        print("Service %s removed" % (name,))
        print("FIXME: Remove printer from dropdown menu here")
        # self.controlview.printerCombo.removeItem(???) # FIXME: Remove the correct one
        # Do we ever get remove_service notices when a printer is shut down?

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        print("Service %s added, service info: %s" % (name, info))

        # Try zeroconf cache first
        info = ServiceInfo(type, name, properties = {})
        for record in zeroconf.cache.entries_with_name(name.lower()):
            info.update_record(zeroconf, time.time(), record)
        for record in zeroconf.cache.entries_with_name(info.server):
            info.update_record(zeroconf, time.time(), record)
            if info.address and info.address[:2] != b'\xa9\xfe': # 169.254.x.x addresses are self-assigned; reject them
                break
        # Request more data if info from cache is not complete
        if not info.address or not info.port:
            info = zeroconf.get_service_info(type, name)
            if not info:
                print("Could not get information about %s" % name)
                return
        if info.address and info.port:
            address = '.'.join(map(lambda n: str(n), info.address))

        self.controller.list_of_printing_services.add(address)



class Controller(QObject):
    def __init__(self, app, local_path='', progress_bar=None):
        super(Controller, self).__init__()
        logging.info('Local path: ' + local_path)
        self.view = []

        #this flag is only for development only, Development = True, Production = False
        self.development_flag = False
        progress_bar(10)

        self.app_config = AppParameters(self, local_path)

        self.printing_parameters = PrintingParameters(self.app_config, self)
        progress_bar(30)

        self.analyzer = Analyzer(self)
        self.gcode = None

        #looking for printing services
        self.zeroconf = Zeroconf()
        self.listener = MyListener(self)
        self.browser = ServiceBrowser(self.zeroconf, "_octoprint._tcp.local.", self.listener)

        self.default_printing_service = None
        self.list_of_printing_services = set()
        self.print_on_service = False

        self.printing_settings = {}
        self.settings = {}
        if not self.settings:
            self.settings['debug'] = self.app_config.config.getboolean('settings', 'debug')
            self.settings['automatic_placing'] = self.app_config.config.getboolean('settings', 'automatic_placing')
            self.settings['language'] = self.app_config.config.get('settings', 'language')
            self.settings['printer'] = self.app_config.config.get('settings', 'printer')
            self.settings['printer_type'] = self.app_config.config.get('settings', 'printer_type')
            self.settings['analyze'] = self.app_config.config.getboolean('settings', 'analyze')
            self.settings['automatic_update_parameters'] = self.app_config.config.getboolean('settings', 'automatic_update_parameters')

            self.settings['toolButtons'] = {
                'selectButton': False,
                'moveButton': False,
                'rotateButton': False,
                'scaleButton': False,
                'supportButton': False
        }

        self.actual_printer = deepcopy(self.settings['printer'])
        self.actual_printer_mod = ""

        self.gcode_help_button_pressed = False

        self.enumeration = {
            'language': {
                'cs_CZ': 'Czech',
                'en_US': 'English',
                'es_ES': 'Spanish',
		        'de_DE': 'German'
            },
            'printer': {
                'i3': 'i3',
                'i3_mk2': 'i3 mark2'
            },
            'materials': {
                'pla': 'PLA',
                'abs': 'ABS',
                'flex': 'FLEX'
            },
            'quality': {
                'draft': 'Draft',
                'normal': 'Normal',
                'detail': 'Detail',
                'ultradetail': 'Ultra detail'
            }
        }

        self.warning_message_buffer = []


        #variables for help
        self.last_pos = QPoint()
        self.ray_start = [.0, .0, .0]
        self.ray_end = [.0, .0, .0]
        self.hitPoint = [.0, .0, .0]
        self.last_ray_pos = [.0, .0, .0]
        self.original_scale = 0.0
        self.original_scale_point = numpy.array([0.,0.,0.])
        self.origin_rotation_point = numpy.array([0.,0.,0.])
        self.res_old = numpy.array([0., 0., 0.])
        self.render_status = 'model_view'   #'gcode_view'
        self.status = 'edit'
        self.is_model_loaded = False
        self.canceled = False
        self.filament_use = ''
        self.resolution_of_texture = 16
        self.soluble_extruder = -1

        #event flow flags
        self.mouse_double_click_event_flag = False
        self.mouse_press_event_flag = False
        self.mouse_move_event_flag = False
        self.mouse_release_event_flag = False
        self.tool_press_event_flag = False
        self.tool_helper_press_event_flag = False
        self.object_select_event_flag = False
        self.cursor_over_object = False

        #scene work flags
        self.scene_was_saved = False
        self.scene_was_generated = False
        self.gcode_was_saved = False
        self.scene_is_not_empty = True

        self.printer_number_of_materials = False

        self.gcode_layer = '0.0'
        self.gcode_draw_from_button = True

        self.over_object = False
        self.models_selected = False
        self.advance_settings = False
        self.incompatible_materials = False

        self.analyze_result = {}

        self.app = app
        self.app_parameters = app.arguments()
        #calculate dpi coeficient for scale of widgets
        self.dpi_coef = app.desktop().logicalDpiX() / 96.
        self.dpi_scale = 0 if self.dpi_coef == 1.0 else 2

        print("Dpi coef: " + str(self.dpi_coef))
        print("Dpi scale: " + str(self.dpi_scale))

        self.translator = QTranslator()
        self.set_language(self.settings['language'])
        progress_bar(40)

        progress_bar(85)
        self.slicer_manager = SlicerEngineManager(self)

        self.scene = AppScene(self)
        progress_bar(90)
        self.view = PrusaControlView(self)
        self.update_object_extruders()

        progress_bar(92)

        self.tools = self.view.get_tool_buttons()
        self.tool = ''
        self.camera_move = False
        self.camera_rotate = False
        self.view.update_gui_for_material()
        progress_bar(95)

        printer_settings = self.printing_parameters.get_printer_parameters(self.settings['printer'])
        self.printer_number_of_materials = printer_settings['multimaterial']
        if self.printer_number_of_materials > 1:
            self.single_material_mode = False
            self.view.set_multimaterial_gui_on(True)
        else:
            self.view.set_multimaterial_gui_off(True)

        progress_bar(97)


        #logging.info('Parameters: %s' % ([unicode(i.toUtf8(), encoding="UTF-8") for i in self.app_parameters]))

        #print(str(type(self.app_parameters)))
        if len(self.app_parameters) >= 3:
            for file in self.app_parameters[2:]:
                #logging.info('%s' %unicode(file.toUtf8(), encoding="UTF-8"))
                #self.open_file(unicode(file.toUtf8(), encoding="UTF-8"))
                self.open_file(file)

        progress_bar(99)

        self.message_object00 = ""
        self.message_object01 = ""
        self.message_object02 = ""
        self.message_object03 = ""
        self.message_object04 = ""
        self.message_object05 = ""

        self.show_message_on_status_bar("Ready")
        self.create_messages()

        self.single_material_mode = False

        if self.is_multimaterial() and not self.is_single_material_mode():
            self.add_wipe_tower()

    def update_object_extruders(self):
        self.view.update_object_extruders_cb()

    def open_color_pick_dialog1(self):
        self.view.open_color_pick_dialog1()

    def open_color_pick_dialog2(self):
        self.view.open_color_pick_dialog2()

    def open_color_pick_dialog3(self):
        self.view.open_color_pick_dialog3()

    def open_color_pick_dialog4(self):
        self.view.open_color_pick_dialog4()

    def get_extruder_color(self, extruder_number):
        #print(extruder_number)
        #print(self.view.extruder1_color)
        extruders_color_lst = [self.view.extruder1_color, self.view.extruder2_color, self.view.extruder3_color, self.view.extruder4_color]
        return extruders_color_lst[extruder_number-1]


    def is_multimaterial(self):
        if self.printer_number_of_materials > 1:
            return True
        else:
            return False
        return False

    def set_unset_single_material_mode(self):
        if not self.is_multimaterial():
            return

        self.single_material_mode = self.view.single_material_mode_checkbox.isChecked()

        if self.single_material_mode:
            #set single material GUI
            #print("set single material mode")
            self.set_printer_mod(self.is_actual_printer_multimode())
            self.view.set_multimaterial_gui_off()
            self.remove_wipe_tower()
            self.update_scene()
            self.incompatible_materials = False
        else:
            #set multi material GUI
            #print("set multimaterial mode")
            self.set_printer_mod("")
            self.view.set_multimaterial_gui_on()
            self.change_of_wipe_tower_settings(1)
            self.update_wipe_tower()
            self.update_scene()


        self.view.update_gui_for_material(1)

    def is_actual_printer_multimode(self):
        data = self.printing_parameters.get_printer_parameters(self.actual_printer)['material_mode']
        if not data == "":
            return data
        else:
            return ""

    def is_single_material_mode(self):
        if self.is_multimaterial():
            return self.single_material_mode
        else:
            True

    def set_analyze_result_messages(self, result):
        self.analyze_result = result

    def filtrate_warning_msgs(self):
        self.warning_message_buffer = []
        if self.analyze_result:
            if self.analyze_result['support'] and self.view.supportCombo.currentIndex() == 0:
                self.warning_message_buffer.append(u"• " + self.message_object02)

            if self.analyze_result['brim'] and self.view.brimCheckBox.isChecked() == False:
                self.warning_message_buffer.append(u"• " + self.message_object03)

        if self.incompatible_materials:
            self.warning_message_buffer.append(u"• " + self.message_object04)


        if self.scene.is_collision_of_wipe_tower_and_objects():
            self.warning_message_buffer.append(u"• " + self.message_object05)



    def get_warnings(self):
        messages = self.scene.get_warnings()
        self.filtrate_warning_msgs()
        return messages + self.warning_message_buffer


    def create_messages(self):
        self.message_object00 = self.tr("Object ")
        self.message_object01 = self.tr(" is out of printable area!")
        self.message_object02 = self.tr("Scene is hard to print without support.")
        self.message_object03 = self.tr("For better adhesion turn Brim parametr on.")
        self.message_object04 = self.tr("Incompatible materials, its possible the print will fail.")
        self.message_object05 = self.tr("Collision of wipe tower and object.")


    def check_version(self):
        if not self.app_config.is_version_actual:
            ret = self.view.show_new_version_message()
            if ret == QMessageBox.Yes:
                self.open_web_browser(self.app_config.prusacontrol_update_page)

    def actualize_extruders(self):
        self.show_warning_if_used_materials_are_not_compatible()
        self.actualize_extruder_set()

    def actualize_extruder_set(self):
        if self.is_multimaterial() and not self.is_single_material_mode():
            pass
        else:
            return

        extruders_set_tmp = list(set([ m.extruder for m in self.scene.get_models(with_wipe_tower=False)]))

        if self.view.get_support_option() >=1 :
            extruders_set_tmp.append(self.soluble_extruder)
            extruders_set = list(extruders_set_tmp)
        else:
            extruders_set = list(extruders_set_tmp)

        if 1 in extruders_set:
            #self.view.extruder1_l.setStyleSheet("font-weight: bold;")
            self.view.extruder1_l.setStyleSheet("QLabel { font-weight: bold;}")
            self.view.extruder1_l.setToolTip(self.view.used_extruder_tooltip)
        else:
            self.view.extruder1_l.setStyleSheet("font-weight: normal;")
            self.view.extruder1_l.setToolTip("")

        if 2 in extruders_set:
            self.view.extruder2_l.setStyleSheet("QLabel { font-weight: bold;}")
            self.view.extruder2_l.setToolTip(self.view.used_extruder_tooltip)
        else:
            self.view.extruder2_l.setStyleSheet("font-weight: normal;")
            self.view.extruder2_l.setToolTip("")

        if 3 in extruders_set:
            self.view.extruder3_l.setStyleSheet("QLabel { font-weight: bold;}")
            self.view.extruder3_l.setToolTip(self.view.used_extruder_tooltip)
        else:
            self.view.extruder3_l.setStyleSheet("font-weight: normal;")
            self.view.extruder3_l.setToolTip("")

        if 4 in extruders_set:
            self.view.extruder4_l.setStyleSheet("QLabel { font-weight: bold;}")
            self.view.extruder4_l.setToolTip(self.view.used_extruder_tooltip)
        else:
            self.view.extruder4_l.setStyleSheet("font-weight: normal;")
            self.view.extruder4_l.setToolTip("")


        self.update_wipe_tower()




    def exit_event(self):
        self.zeroconf.close()

        if self.status in ['loading_gcode']:
            self.analyzer.cancel_analyz()
            self.gcode.cancel_parsing_gcode()
            return True
        elif self.status in ['generating']:
            self.analyzer.cancel_analyz()
            ret = self.view.show_exit_message_generating_scene()
            if ret == QMessageBox.Yes:
                self.cancel_generation()
                return True
            elif ret == QMessageBox.No:
                return False
        elif self.is_something_to_save() and not self.scene_was_saved:
            self.analyzer.cancel_analyz()
            ret = self.view.show_exit_message_scene_not_saved()
            if ret == QMessageBox.Save:
                self.save_project_file()
                return True
            elif ret == QMessageBox.Discard:
                return True
            elif ret == QMessageBox.Cancel:
                return False
        else:
            self.analyzer.cancel_analyz()
            return True



    def is_something_to_save(self):
        models_lst = self.scene.get_models(with_wipe_tower=False)
        if len(models_lst) == 0:
            return False
        else:
            return True

    def get_informations(self):
        if not self.gcode:
            return

        printing_time = self.gcode.printing_time
        filament_length = self.filament_use

        printing_time_str = self.convert_printing_time_from_seconds(printing_time)
        filament_length_str = self.convert_filament_length_units(filament_length)

        data = {'info_text': 'info total:',
                'printing_time': printing_time_str,
                'filament_lenght': filament_length_str}

        return data

    def convert_printing_time_from_seconds(self, seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)

        if h == 0:
            return "{:2.0f}min".format(m)
        else:
            return "{:2.0f}h {:2.0f}min".format(h, m)

    def convert_filament_length_units(self, filament_lenght_mm):
        if not filament_lenght_mm:
            return ""
        original_filament_lenght = float(filament_lenght_mm[:-2])
        original_units = filament_lenght_mm[-2:]
        if original_units == "mm":
            if original_filament_lenght >= 1000.:
                recalculated_filament_lenght = original_filament_lenght*0.001
                recalculated_units = "m"
            elif original_filament_lenght >= 10.:
                recalculated_filament_lenght = original_filament_lenght * 0.1
                recalculated_units = "cm"
            elif original_filament_lenght >= 1.:
                recalculated_filament_lenght = original_filament_lenght
                recalculated_units = original_units

            recalculated_filament_lenght_str = "{:.1f}".format(recalculated_filament_lenght)
            recalculated_filament_lenght_str = recalculated_filament_lenght_str.rstrip("0")
            recalculated_filament_lenght_str = recalculated_filament_lenght_str.rstrip(".")
            new_filament_format = "{}{}".format(recalculated_filament_lenght_str, recalculated_units)
        else:
            new_filament_format = "{}".format(filament_lenght_mm)
        return new_filament_format

    def clear_event_flag_status(self):
        self.mouse_double_click_event_flag = False
        self.mouse_press_event_flag = False
        self.mouse_move_event_flag = False
        self.mouse_release_event_flag = False
        self.tool_press_event_flag = False
        self.object_select_event_flag = False
        self.tool_helper_press_event_flag = False
        self.cursor_over_object = False

    def clear_gcode(self):
        self.gcode = None
        self.gcode_layer = '0.0'
        self.gcode_draw_from_button = False


    def write_config(self):
        config = RawConfigParser()
        config.add_section('settings')
        config.set('settings', 'printer', self.settings['printer'])
        config.set('settings', 'printer_type', self.settings['printer_type'])
        config.set('settings', 'debug', str(self.settings['debug']))
        config.set('settings', 'automatic_placing', str(self.settings['automatic_placing']))
        config.set('settings', 'language', self.settings['language'])
        config.set('settings', 'analyze', self.settings['analyze'])
        config.set('settings', 'automatic_update_parameters', self.settings['automatic_update_parameters'])


        with open(self.app_config.config_path, 'w') as configfile:
            config.write(configfile)

    def set_basic_settings(self):
        self.advance_settings = False
        self.view.object_variable_layer_box.setVisible(False)
        self.view.object_group_box.setVisible(True)
        self.update_scene()

    def set_advance_settings(self):
        self.advance_settings = True
        self.view.object_group_box.setVisible(False)
        self.view.object_variable_layer_box.setVisible(True)
        #self.view.variable_layer_widget.set_model(self.ac)
        self.update_scene()

    def set_gcode_slider(self, min, max, min_l, max_l):
        self.view.gcode_slider.setMinimum(min, min_l)
        self.view.gcode_slider.setMaximum(max, max_l)


    def set_gcode_instance(self, gcode_instance):
        self.gcode = gcode_instance
        self.gcode.done_loading_callback = self.set_gcode
        self.gcode.writing_done_callback = self.set_saved_gcode
        self.set_gcode()

    def print_progress(self, progress):
        print("Progress: " + str(progress))


    def read_gcode(self, filename = ''):
        #print("reading gcode")
        if filename:
            self.gcode = GCode(filename, self, self.set_gcode, self.set_saved_gcode)
        else:
            self.gcode = GCode(self.app_config.tmp_place + 'out.gcode', self, self.set_gcode, self.set_saved_gcode)

        self.view.set_cancel_of_loading_gcode_file()
        self.status = 'loading_gcode'
        self.view.disable_editing()
        self.gcode.read_in_thread(self.set_progress_bar, self.set_gcode)


    def set_saved_gcode(self):
        self.set_progress_bar(100)
        self.status = 'generated'
        self.set_gcode_view()
        self.show_message_on_status_bar(self.view.tr("GCode saved"))


    def set_gcode(self):
        #print("Set gcode")
        if not self.gcode.is_loaded:
            return
        self.status = 'generated'

        min = 0
        max = len(self.gcode.data_keys) - 1

        min_l = float(self.gcode.data_keys[0])
        max_l = float(self.gcode.data_keys[-1])

        self.set_gcode_slider(min, max, min_l, max_l)

        #What layer had to be show at start
        self.gcode_layer = self.gcode.data_keys[1]

        self.view.gcode_label.setText(self.gcode.data_keys[0])
        self.view.gcode_slider.setValue(float(self.gcode.data_keys[0]))

        self.set_gcode_view()


    def set_variable_layer_cursor(self, double_value):
        for m in self.scene.models:
            if m.isVisible and m.selected:
                m.z_cursor = double_value
        self.update_scene()


    def set_gcode_layer(self, value):
        self.gcode_layer = self.gcode.data_keys[value]
        self.update_scene()
        #self.view.update_scene()

    def set_gcode_draw_from_button(self, val):
        self.gcode_draw_from_button = val

    def scene_was_sliced(self):
        #self.set_save_gcode_button()
        #self.read_gcode()
        self.view.gcode_slider.init_points()
        self.set_gcode_view()
        self.status = 'generated'
        self.app.alert(self.view, 0)

    def check_rotation_helper(self, event):
        #print("check rotation")
        id = self.get_id_under_cursor(event)
        if self.is_some_tool_under_cursor(id):
            self.view.update_scene()

    def unselect_tool_buttons(self):
        for tool in self.tools:
            tool.unpress_button()


    def set_gcode_view(self):
        self.unselect_objects()
        self.render_status = 'gcode_view'
        self.open_gcode_gui()

    def set_model_edit_view(self):
        self.render_status = 'model_view'
        self.set_generate_button()
        self.view.enable_editing()
        self.status = 'edit'
        #self.editable = editable
        self.view.close_gcode_view()
        self.show_message_on_status_bar("")

    def open_gcode_gui(self):
        self.view.disable_editing()
        self.view.open_gcode_view()

    def close_gcode_gui(self):
        self.view.close_gcode_view()

    def set_language(self, language):
        full_name = self.app_config.local_path + 'translation/' + language + '.qm'
        self.translate_app(full_name)

    def translate_app(self, translation=""):
        if translation == "":
            translation = self.app_config.local_path + "translation/en_US.qm"

        self.translator.load(translation)
        self.app.installTranslator(self.translator)
        if self.view:
            self.view.retranslateUI()

    def cancel_generation(self):
        self.slicer_manager.cancel()

    def get_enumeration(self, section, enum):
        return self.enumeration[section][enum] if section in self.enumeration and enum in self.enumeration[section] else str(section)+':'+str(enum)

    def get_printer_name(self):
        #TODO:Add code for read and detect printer name
        return "Original Prusa i3"

    def get_firmware_version_number(self):
        #TODO:Add code for download firmware version
        return '1.0.1'

    def get_printers_labels_ls(self, only_visible=False):
        printers = self.printing_parameters.get_printers_parameters()
        if only_visible and 'visible' in printers[list(printers.keys())[0]]:
            unsorted = [[printers[printer]["label"], [printers[printer]['sort']]] for printer in printers if printers[printer]['visible'] == 1]
            sort_lst = sorted(unsorted, key=lambda mem: mem[1])
            return [a[0] for a in sort_lst]
        else:
            unsorted = [[printers[printer]["label"], [printers[printer]['sort']]] for printer in printers]
            sort_lst = sorted(unsorted, key=lambda mem: mem[1])
            return [a[0] for a in sort_lst]

    def get_printers_names_ls(self, only_visible=False):
        return self.printing_parameters.get_printers_names(only_visible)

    def get_printer_variations_labels_ls(self, printer_name):
        first = 0
        data = self.printing_parameters.get_printer_parameters(printer_name)
        if 'sort' in data["printer_type"][list(data["printer_type"])[0]] and 'first' in data["printer_type"][list(data["printer_type"])[0]]:
            unsorted = [[data["printer_type"][printer_type]["label"], data["printer_type"][printer_type]['sort'], data["printer_type"][printer_type]['first']] for printer_type in data["printer_type"]]
            sort_lst = sorted(unsorted, key=lambda mem: mem[1])
            for i, d in enumerate(sort_lst):
                if d[2] == 1:
                    first = i
                    break
            return [mem[0] for mem in sort_lst], first
        else:
            return [data["printer_type"][printer_type]["label"] for printer_type in data["printer_type"]], first

    def get_printer_variations_names_ls(self, printer_name):
        first = 0
        data = self.printing_parameters.get_printer_parameters(printer_name)
        if 'sort' in data["printer_type"][list(data["printer_type"])[0]] and 'first' in data["printer_type"][list(data["printer_type"])[0]]:
            unsorted = [[data["printer_type"][printer_type]["name"], data["printer_type"][printer_type]['sort'], data["printer_type"][printer_type]['first']] for printer_type in data["printer_type"]]
            sort_lst = sorted(unsorted, key=lambda mem: mem[1])
            for i, d in enumerate(sort_lst):
                if d[2] == 1:
                    first = i
                    break
            return [mem[0] for mem in sort_lst], first
        else:
            return list(data["printer_type"]), first

    def get_printer_materials_names_ls(self, printer_name):
        #return self.printing_settings['materials']
        #return [i['label'] for i in self.printing_settings['materials'] if i['name'] not in ['default']]
        return self.printing_parameters.get_materials_for_printer(printer_name).keys()

    def get_printer_materials_labels_ls(self, printer_name):
        first_index = 0
        data = self.printing_parameters.get_materials_for_printer(printer_name)
        list = [[data[material]['label'], data[material]["sort"], data[material]["first"]] for material in data]
        list = sorted(list, key=lambda a: a[1])
        for i, data in enumerate(list):
            if data[2] == 1:
                first_index = i
                break
        return [a[0] for a in list], first_index

    def get_printer_material_quality_labels_ls_by_material_name(self, material_name):
        #return [self.printing_parameters.get_materials_quality_for_printer(self.actual_printer, material_name)['quality'][i]['label']
        #        for i in self.printing_parameters.get_materials_quality_for_printer(self.actual_printer, material_name)['quality']]
        first_index = 0
        data = self.printing_parameters.get_materials_quality_for_printer(self.get_actual_printer(), material_name)['quality']
        list = [[data[quality]['label'], data[quality]["sort"], data[quality]["first"]] for quality in data]
        list = sorted(list, key=lambda a: a[1])
        for i, data in enumerate(list):
            if data[2] == 1:
                first_index = i
                break
        return [a[0] for a in list], first_index

    def get_material_name_by_material_label(self, material_label):
        data = self.printing_parameters.get_materials_for_printer(self.get_actual_printer())
        for i in data:
            if data[i]['label']==material_label:
                return i
        return None

    def get_material_quality_name_by_quality_label(self, material_name, quality_label):
        data = self.printing_parameters.get_materials_for_printer(self.get_actual_printer())[material_name]
        for i in data["quality"]:
            if data["quality"][i]['label'] == quality_label:
                return i
        return None



    def get_printer_material_quality_labels_ls_by_material_label(self, material_label):
        materials_ls = self.printing_parameters.get_materials_for_printer(self.get_actual_printer())
        material_name = ""
        for material in materials_ls:
            if materials_ls[material]['label'] == material_label:
                material_name = material
                break

        return self.get_printer_material_quality_labels_ls_by_material_name(material_name)

    def get_printer_material_quality_names_ls(self, material):
        # return [i['label'] for i in self.printing_settings['materials'][index]['quality'] if i['name'] not in ['default']]
        data = self.printing_parameters.get_materials_quality_for_printer(self.get_actual_printer(), material)['quality']
        list = [[quality, data[quality]["sort"]] for quality in data]
        list = sorted(list, key=lambda a: a[1])
        return [a[0] for a in list]
        #return [i for i in self.printing_parameters.get_materials_quality_for_printer(self.get_actual_printer(), material)['quality']]

    def get_printing_settings_for_material_in_extruder(self, extruder_number):
        if extruder_number in [1, 2, 3, 4]:
            if extruder_number == 1:
                return self.get_printing_settings_for_material_by_label(self.view.extruder1_c.currentText())
            elif extruder_number == 2:
                return self.get_printing_settings_for_material_by_label(self.view.extruder2_c.currentText())
            elif extruder_number == 3:
                return self.get_printing_settings_for_material_by_label(self.view.extruder3_c.currentText())
            elif extruder_number == 4:
                return self.get_printing_settings_for_material_by_label(self.view.extruder4_c.currentText())
        else:
            return None


    def get_printing_settings_for_material_by_name(self, material_name):
        # material = self.printing_settings['materials'][material_index]
        printing_settings_tmp = []
        printing_settings_tmp = self.printing_parameters.get_materials_for_printer(self.get_actual_printer())
        material_printing_setting = printing_settings_tmp[material_name]

        return material_printing_setting

    def get_printing_settings_for_material_by_label(self, material_label):
        printing_settings_tmp = []
        for material in self.printing_parameters.get_materials_for_printer(self.get_actual_printer()):
            if self.printing_parameters.get_materials_for_printer(self.get_actual_printer())[material]["label"] == material_label:
                printing_settings_tmp = self.printing_parameters.get_materials_for_printer(self.get_actual_printer())[material]
                break

        return printing_settings_tmp

    def update_mm_material_settings(self):
        #print("Update mm material settigns")
        # get combobox materials
        soluble_material_tmp = []

        if not self.is_multimaterial():
            return

        soluble_material_tmp.append(self.get_printing_settings_for_material_by_label(self.view.extruder1_c.currentText())["soluble"])
        soluble_material_tmp.append(self.get_printing_settings_for_material_by_label(self.view.extruder2_c.currentText())["soluble"])
        soluble_material_tmp.append(self.get_printing_settings_for_material_by_label(self.view.extruder3_c.currentText())["soluble"])
        soluble_material_tmp.append(self.get_printing_settings_for_material_by_label(self.view.extruder4_c.currentText())["soluble"])
        soluble_material = soluble_material_tmp[:self.printer_number_of_materials]

        # if one of them soluble then add special support form, if not support combo without it
        if 1 in soluble_material:
            soluble_extruders = [i+1 for i, m in enumerate(soluble_material) if m == 1]
            self.soluble_extruder = soluble_extruders[0]
            self.set_special_support_settings()
        else:
            self.soluble_extruder = -1
            self.set_normal_support_settings()


        self.show_warning_if_used_materials_are_not_compatible()
        self.actualize_extruder_set()



    def show_warning_if_used_materials_are_not_compatible(self):
        if self.is_multimaterial() and not self.is_single_material_mode():
            pass
        else:
            self.incompatible_materials = False
            return
        list_of_materials = [self.get_printing_settings_for_material_by_label(self.view.extruder1_c.currentText())["name"],
                             self.get_printing_settings_for_material_by_label(self.view.extruder2_c.currentText())["name"],
                             self.get_printing_settings_for_material_by_label(self.view.extruder3_c.currentText())["name"],
                             self.get_printing_settings_for_material_by_label(self.view.extruder4_c.currentText())["name"]]

        compatible_with_lst = []
        # if some materials are not compatible
        # read compatible with list for all selected materials
        compatible_with_lst.append(
            self.check_compatible_with_lst(self.get_printing_settings_for_material_by_label(
                self.view.extruder1_c.currentText())["compatible_with"]))
        compatible_with_lst.append(
            self.check_compatible_with_lst(self.get_printing_settings_for_material_by_label(
                self.view.extruder2_c.currentText())["compatible_with"]))
        compatible_with_lst.append(
            self.check_compatible_with_lst(self.get_printing_settings_for_material_by_label(
                self.view.extruder3_c.currentText())["compatible_with"]))
        compatible_with_lst.append(
            self.check_compatible_with_lst(self.get_printing_settings_for_material_by_label(
                self.view.extruder4_c.currentText())["compatible_with"]))


        # find out which extruders are used and create filter it
        used_extruders_tmp = list(set([m.extruder-1 for m in self.scene.get_models(with_wipe_tower=False)]))

        if self.view.get_support_option() >=1 :
            used_extruders_tmp.append(self.soluble_extruder-1)

        used_extruders = [i in used_extruders_tmp for i in range(0,4)]
        #print(used_extruders_tmp)
        #print(used_extruders)


        show_warning = False
        # generate warning message if some material is not compatible
        if len(used_extruders_tmp) > 1:
            # compare compatibility
            #print("List compatibility: " + str(compatible_with_lst))
            #print("List pouzitych extruderu: " + str(used_extruders))

            filtrated_used_materials = list(compress(list_of_materials, used_extruders))
            filtrated_compatible_lst = list(compress(compatible_with_lst, used_extruders))

            for i, material in enumerate(filtrated_used_materials):
                #print("Material: " + str(material))
                compatible_materials = [ mat for o, mat in enumerate(filtrated_compatible_lst) if not i==o ]
                #print("Compatible materials: " + str(compatible_materials))
                for compat_mat in compatible_materials:
                    if not material in compat_mat:
                        #print("Nekompatibilni")
                        show_warning = True

        if show_warning:
            self.incompatible_materials = True
        else:
            self.incompatible_materials = False
        self.update_scene()


    def check_compatible_with_lst(self, lst):
        if lst == []:
            return list(self.get_printer_materials_names_ls(self.get_actual_printer()))
        else:
            return lst


    def set_special_support_settings(self):
        self.view.set_special_support_settings()

    def set_normal_support_settings(self):
        self.view.set_normal_support_settings()


    def get_infill_ls_and_index_of_default(self, default):
        first = 0
        #infill_ls = ["0%", "10%", "15%", "20%", "30%", "50%", "70%"]
        infill_ls = [self.tr("Hollow/Shell - ") + "0%",
                     self.tr("Sparse - ") + "10%",
                     self.tr("Light - ") + "15%",
                     self.tr("Standard - ") + "20%",
                     self.tr("Dense - ") + "30%",
                     self.tr("Denser - ") + "50%",
                     self.tr("Solid - ") + "70%"]
        for i, data in enumerate(infill_ls):
            if default in data:
                first = i
                break

        return infill_ls, first

    def get_infill_values_ls(self):
        return [0, 10, 15, 20, 30, 50, 70]

    def get_actual_printing_data(self):
        #GUI parameters
        gui_parameters = self.view.get_actual_printing_data()
        #Scene parameters(wipe tower possition)
        scene_parameters = self.scene.get_wipe_tower_possition_and_size()

        #multimaterial parameters
        multimat = dict()
        multimat["is_multimat"] = int(self.is_multimaterial() and not self.is_single_material_mode())

        out = {}

        for param in (gui_parameters, scene_parameters, multimat):
            out.update(param)

        return out


    def open_cancel_generating_dialog(self):
        ret = self.view.show_cancel_generating_dialog_and_load_file()
        if ret == QMessageBox.Yes:
            self.cancel_generation()
            return True
        elif ret == QMessageBox.No:
            return False


    def open_cancel_gcode_reading_dialog(self):
        ret = self.view.show_cancel_generating_dialog_and_load_file()
        if ret == QMessageBox.Yes:
            self.cancel_gcode_loading()
            return True
        elif ret == QMessageBox.No:
            return False

    def generate_button_pressed(self):
        if self.status in ['edit', 'canceled']:
            self.clear_tool_button_states()

            #prepared to be g-code generated
            self.canceled = False
            self.close_object_settings()
            self.view.disable_editing()

            if not self.canceled:
                self.generate_gcode()
                self.set_cancel_button()
                self.status = 'generating'
        elif self.status == 'saving_gcode':
            self.gcode.cancel_writing_gcode()
            self.status = 'generated'
            self.view.open_gcode_view()

        elif self.status == 'generating':
            #generating in progress
            self.cancel_generation()
            self.cancel_gcode_loading()
            self.status = 'canceled'
            self.view.enable_editing()
            self.set_generate_button()

        elif self.status == 'loading_gcode':
            self.cancel_gcode_loading()
            self.show_message_on_status_bar("")
        elif self.status == 'generated':
            #already generated
            if self.print_on_service:
                self.print_on_actual_service()
            else:
                self.save_gcode_file()

    def print_on_actual_service(self):
        #TODO: Ask if prusacontrol dont have apikey for service, other way use one from file
        apikey = 'CA54B5013E8C4C4B8BE6031F436133F5'

        http = urllib3.PoolManager()

        print("Printing on octoprint:")
        url = "http://" + self.default_printing_service + '/api/files/local'
        print("Sending to %s" % (url))

        with open(self.app_config.tmp_place + 'out.gcode') as fp:
            binary_data = fp.read()
            print("Suggested gcode filename: " + self.generate_gcode_filename())
            # TODO:Add check if printer is in use, denide to upload/print new thing
            r = http.request('POST',
                             url,
                             fields={'file': ('%s.gcode' % self.generate_gcode_filename(), binary_data),
                                     "command": "select", "print": 'true'},
                             headers={'X-Api-Key': apikey})

        #TODO:Add progress bar for uploading gcode to printer




        print("Start sending gcode")
        print("...")
        #r = post(url, files=files)
        print(str(r.status))
        print("gcode recieved OK")
        print("starting printing")
        print("Printing on OctoPrint")


    def cancel_gcode_loading(self):
        if self.gcode:
            self.gcode.cancel_parsing_gcode()
        self.gcode = None
        self.status = 'canceled'
        self.disable_generate_button()
        self.set_generate_button()
        self.set_progress_bar(0)
        #print("Cancel gcode loading end")


    #TODO:Better way
    def generate_gcode_filename(self):
        suggest_filename = ""
        filename = ""
        '''
        list = []
        if len(self.scene.models) == 1:
            filename = self.scene.models[0].filename
            suggest_filename = filename.split(".")
            suggest_filename = suggest_filename[0]
        else:
            #for m in self.scene.models:
            #    list.append(m.filename)
            suggest_filename = "mix"
        '''
        for m in self.scene.models:
            if m.isVisible and not m.is_wipe_tower:
                filename = m.filename
                break

        if filename == '' and self.gcode:
            suggest_filename = self.gcode.filename
        else:
            suggest_filename = filename.split(".")
            suggest_filename = suggest_filename[0]
            data = self.get_actual_printing_data()
            material_name = data['material']

            quality_name = data['quality']
            material_names_lst = [mat.split('_')[-1] for mat in material_name]

            material_info = "_".join(material_names_lst)
            suggest_filename += "_" + material_info.upper() + "_" + quality_name.upper()

        if self.is_multimaterial() and not self.is_single_material_mode():
            suggest_filename = suggest_filename + "_MM"


        return suggest_filename


    def open_web_browser(self, url):
        webbrowser.open(url, 1)

    def set_printer(self, name):
        #index = [i for i, data in enumerate(self.printers) if data['name']== name]
        #print("Setting actual printer on: " + str(name))
        self.actual_printer = deepcopy(name)
        self.settings['printer'] = deepcopy(name)
        self.actual_printer_mod = ""

    def set_printer_mod(self, special_mode):
        self.actual_printer_mod = special_mode

    def get_actual_printer(self):
        if self.actual_printer_mod:
            return self.actual_printer_mod
        else:
            return self.actual_printer

    def change_of_wipe_tower_settings(self, value):
        #print("change of wipe tower settings: " +str(value))
        # value reduce 0 - small wipe tower 5
        # value normal 1 - normal wipe tower 15
        # value increase/soluble 2 - bigger wipe tower 20

        if value == 0:
            self.scene.wipe_tower_size_y = 7.5
        elif value == 1:
            self.scene.wipe_tower_size_y = 15.
        elif value == 2:
            self.scene.wipe_tower_size_y = 20.


        self.recalculate_wipe_tower()



    def send_feedback(self):
        if self.settings['language'] == 'cs_CZ':
            self.open_web_browser(self.app_config.prusacontrol_questionnaire_cz)
        else:
            self.open_web_browser(self.app_config.prusacontrol_questionnaire_en)

    def open_help(self):
        self.open_web_browser(self.app_config.prusacontrol_help_page)

    def open_shop(self):
        self.open_web_browser(self.app_config.prusa_eshop_page)

    def set_save_gcode_button(self):
        self.view.set_save_gcode_button()

    def set_cancel_button(self):
        self.view.set_cancel_button()

    def set_generate_button(self):
        self.view.set_generate_button()
        if not self.scene.is_scene_printable():
            self.disable_generate_button()

    def update_gui(self):
        self.view.update_gui()

    def set_progress_bar(self, value):
        self.view.progressBar.setValue(value)

    def get_view(self):
        return self.view

    def get_model(self):
        return self.scene

    def open_printer_info(self):
        self.view.open_printer_info_dialog()

    def set_gcode_help_button_pressed(self):
        self.gcode_help_button_pressed = True
        self.update_scene()

    def set_gcode_help_button_released(self):
        self.gcode_help_button_pressed = False
        self.view.gcode_help_b.setChecked(False)
        self.update_scene()

    def show_gcode_help(self):
        if self.render_status == 'gcode_view' and self.gcode_help_button_pressed:
            return True
        return False

    def open_update_firmware(self):
        self.view.open_firmware_dialog()

    def open_project_file(self, url=None):
        if self.is_something_to_save():
            ret = self.view.open_project_asking_dialog()
            if ret == False:
                return
            elif ret == 'Open':
                self.scene.clear_scene()
            elif ret == 'Insert':
                print("Nic nebudu mazat scena zustane stejna")

        if url:
            data = url
        else:
            data = self.view.open_project_file_dialog()
        #logging.debug('open project file %s' %data)
        self.import_project(data)
        self.show_warning_if_used_materials_are_not_compatible()
        self.actualize_extruder_set()
        self.show_message_on_status_bar(self.view.tr("Project loaded"))

    def save_project_file(self):
        path = self.view.save_project_file_dialog()
        if path == '':
            return
        filename = path.split('.')
        if filename[-1] in ['prusa', 'PRUSA']:
            filename_out = path
        else:
            filename_out = path + '.prusa'

        self.save_project(filename_out)
        self.show_message_on_status_bar(self.view.tr("Project was saved"))

    def set_print_on(self, printer_text):
        printer_ip = printer_text.split(' ')[-1]
        print("Printer IP: " + str(printer_ip))
        self.default_printing_service = printer_ip
        self.print_on_service = True

    def add_new_octoprint(self):
        print("show dialog for new octoprint service")
        self.open_new_octoprint_dialog()
        print("save octoprint settings")
        print("add new settings to list")

    def open_new_octoprint_dialog(self):
        new_octoprint_settings, ret = self.view.open_new_octoprint_dialog()
        if ret == QMessageBox.Yes:
            return True
        elif ret == QMessageBox.No:
            return False

    def save_gcode_file(self):
        suggested_filename = self.generate_gcode_filename()
        color_change_layers = self.view.gcode_slider.get_color_change_layers()
        color_change_data = self.gcode.get_first_extruding_line_number_of_gcode_for_layers(color_change_layers)
        path = self.view.save_gcode_file_dialog(suggested_filename)
        if path == '':
            return
        filename = path.split('.')
        if filename[-1] in ['gcode', 'GCODE']:
            filename_out = path
        else:
            filename_out = path + '.gcode'
        try:
            self.status = "saving_gcode"
            self.view.saving_gcode()
            #copyfile(self.app_config.tmp_place + "out.gcode", filename_out)
            self.gcode.set_color_change_data(color_change_data)
            self.gcode.write_with_changes_in_thread(self.gcode.filename, filename_out, self.set_progress_bar)

        except Error as e:
            logging.debug('Error: %s' % e)
        except IOError as e:
            logging.debug('Error: %s' % e.strerror)

    def open_gcode_file(self):
        path = self.view.open_gcode_file_dialog()
        self.open_file(path)

    def open_model_file(self):
        data = self.view.open_model_file_dialog()
        #logging.debug('open model#  file %s' %data)
        for path in data:
            #print("File path type: " + str(type(path)))
            self.import_model(path)

    def open_multipart_model(self):
        data = self.view.open_model_file_dialog()
        self.load_multipart_model(data)
        self.actualize_extruder_set()



    def load_multipart_model(self, lst_of_urls):
        self.show_message_on_status_bar(self.tr("Loading multi part model"))
        model_lst = []
        extruder_counter = 1
        for path in lst_of_urls:
            model = ModelTypeStl().load(path, False)
            model.parent = self.scene
            model.is_multipart_model = True
            self.scene.models.append(model)
            model.extruder = extruder_counter
            if extruder_counter <= 3:
                extruder_counter +=1
            else:
                extruder_counter = 1
            model_lst.append(model)


        multiModel = sceneData.MultiModel(model_lst, self.scene)
        self.scene.multipart_models.append(multiModel)

        self.is_model_loaded = True

        self.scene.normalize_group_of_models(model_lst)
        multiModel.update_min_max()

        if self.is_multimaterial():
            self.recalculate_wipe_tower()


    def import_model(self, path, one_model=False):
        self.view.statusBar().showMessage('Load file name: ' + path)

        model = ModelTypeStl().load(path, True)
        model.parent = self.scene
        self.scene.models.append(model)
        if self.settings['automatic_placing'] and not one_model:
            self.scene.automatic_models_position()
        self.scene.clear_history()
        self.scene.save_change(self.scene.models)
        if self.is_multimaterial() and not self.is_single_material_mode():
            self.recalculate_wipe_tower()
        self.update_scene()
        self.is_model_loaded = True
        return model
        #self.view.update_scene()

    def import_project(self, path):
        project_file = ProjectFile(self.scene, path)

        if self.is_multimaterial() and not self.is_single_material_mode():
            self.recalculate_wipe_tower()
        self.update_scene()

        #self.view.update_scene()


    def save_project(self, path):
        self.scene.check_models_name()
        project_file = ProjectFile(self.scene)
        project_file.save(path)
        self.scene_was_saved = True

    def update_scene(self, reset=False):
        self.view.update_scene(reset)
        if self.status in ['edit', 'canceled']:
            if self.scene.is_scene_printable():
                self.enable_generate_button()
            else:
                self.disable_generate_button()

    def update_firmware(self):
        #TODO:Add code for update of firmware
        pass

    def open_object_settings_dialog(self, object_id):
        object_settings = self.view.open_object_settings_dialog(object_id)

    def open_settings(self):
        is_change = False
        if self.status in ['generating', 'generated', 'loading_gcode']:
            editable = False
        else:
            editable = True
        temp_settings, ok = self.view.open_settings_dialog(editable=editable)
        if not ok:
            return

        if not temp_settings['language'] == self.settings['language']:
            self.set_language(temp_settings['language'])

        if not temp_settings['printer'] == self.settings['printer']:
            is_change = True

        printer_settings = self.printing_parameters.get_printer_parameters(temp_settings['printer'])
        self.printer_number_of_materials = printer_settings['multimaterial']

        if is_change:
            self.set_printer(temp_settings['printer'])
            if self.printer_number_of_materials>1:
                self.view.set_multimaterial_gui_on(True)
                #self.view.update_gui_for_material(1)
                self.update_mm_material_settings()
                #self.add_wipe_tower()
                self.update_wipe_tower()
            else:
                self.view.set_multimaterial_gui_off(True)
                #self.view.update_gui_for_material(1)
                self.remove_wipe_tower()
            self.view.update_gui_for_material(1)

        self.settings = temp_settings



    def add_wipe_tower(self):
        self.scene.create_wipe_tower()

    def remove_wipe_tower(self):
        self.scene.remove_wipe_tower()

    def update_wipe_tower(self):
        self.scene.update_wipe_tower()

    def open_about(self):
        self.view.open_about_dialog()

    def generate_gcode(self):
        self.set_progress_bar(int((100. / 9.)))
        if self.scene.models:
            self.save_whole_scene_to_one_prusa_file(self.app_config.tmp_place + "tmp.prusa")
            #if self.is_multimaterial() and not self.is_single_material_mode():
            #    self.save_whole_scene_to_one_prusa_file(self.app_config.tmp_place + "tmp.prusa")
            #else:
            #    self.scene.save_whole_scene_to_one_stl_file(self.app_config.tmp_place + "tmp.stl")
            self.slicer_manager.slice()

    def gcode_generated(self):
        self.view.enable_save_gcode_button()

    def save_whole_scene_to_one_prusa_file(self, path):
        self.save_project(path)
        self.scene_was_saved = False

    def close(self):
        self.analyzer.cancel_analyz()
        self.app.exit()

    def set_print_info_text(self, string):
        #print("Nejaky text ze Sliceru: " + string)
        string = string.split(' ')
        self.filament_use = string[0]
        #self.gcode.set_print_info_text(string[0])

    def scene_was_changed(self):
        if self.status == 'generating':
            self.cancel_generation()
        self.status = 'edit'
        self.scene.analyze_result_data_tmp = []
        self.set_generate_button()
        self.set_progress_bar(0.0)

    def wheel_event(self, event):
        self.view.set_zoom(event.angleDelta().y() / 120)

        event.accept()
        self.update_scene()

    def set_camera_move_function(self):
        self.camera_move=True
        self.camera_rotate=False

    def set_camera_rotation_function(self):
        self.camera_move = False
        self.camera_rotate = True
        self.cursor_over_object = False

    def set_camera_function_false(self):
        self.camera_move = False
        self.camera_rotate = False
        self.cursor_over_object = False

    def is_some_tool_under_cursor(self, object_id):
        #print("Is some tool under cursor")
        for tool in self.tools:
            if tool.id == object_id:
                return True
        return False

    def get_tool_by_id(self, object_id):
        for tool in self.tools:
            if tool.id == object_id:
                return tool
        return None

    def get_object_by_id(self, object_id):
        for model in self.scene.models:
            if object_id == model.id:
                return model
        return None


    def is_some_tool_helper_under_cursor(self, object_id):
        if object_id == 0:
            return False
        for model in self.scene.models:
            if model.is_wipe_tower:
                continue
            if model.selected:
                if model.rotateXId == object_id:
                    model.scalenAxis = []
                    model.selected = True
                    model.rotationAxis = 'x'
                    self.tool = 'rotate'
                    return True
                elif model.rotateYId == object_id:
                    model.scalenAxis = []
                    model.selected = True
                    model.rotationAxis = 'y'
                    self.tool = 'rotate'
                    return True
                elif model.rotateZId == object_id:
                    model.scalenAxis = []
                    model.selected = True
                    model.rotationAxis = 'z'
                    self.tool = 'rotate'
                    return True
                elif model.scaleXId == object_id:
                    model.rotationAxis = []
                    model.selected = True
                    model.scaleAxis = 'x'
                    self.tool = 'scale'
                    return True
                elif model.scaleYId == object_id:
                    model.rotationAxis = []
                    model.selected = True
                    model.scaleAxis = 'y'
                    self.tool = 'scale'
                    return True
                elif model.scaleZId == object_id:
                    model.rotationAxis = []
                    model.selected = True
                    model.scaleAxis = 'z'
                    self.tool = 'scale'
                    return True
                elif model.scaleXYZId == object_id:
                    model.rotationAxis = []
                    model.selected = True
                    model.scaleAxis = 'XYZ'
                    self.tool = 'scale'
                    return True
                else:
                    model.rotationAxis = []
                    model.scalenAxis = []
                    #model.selected = False


    def set_active_tool_helper_by_id(self, object_id):
        pass


    def recalculate_wipe_tower(self):
        #print("calculating wipe tower")
        self.scene.update_wipe_tower()





    @staticmethod
    def is_ctrl_pressed():
        #print("is_ctrl_pressed")
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            return True
        else:
            return False

    def is_object_already_selected(self, object_id):
        #print("is_object_already_selected")
        for model in self.scene.models:
            #object founded
            if object_id == model.id:
                #print("Je model oznaceny: " + str(model.selected))
                if model.selected:
                    #object is selected
                    #print("return True")
                    return True
                else:
                    #object is not selected
                    #print("return False")
                    return False
        #No object with id in scene.models
        return None

    def unselect_objects_and_select_this_one(self, object_id):
        self.unselect_objects()
        one_selected = False
        for model in self.scene.models:
            #object founded
            if object_id == model.id:
                model.selected = True
                one_selected = True
                self.object_select_event_flag = True

        if one_selected:
            return True
        else:
            return False


    def unselect_object(self, object_id):
        for model in self.scene.models:
            # object founded
            if object_id == model.id:
                model.selected = False
                return True
        return False

    def select_object(self, object_id):
        for model in self.scene.models:
            # object founded
            if object_id == model.id:
                model.selected = True
                self.object_select_event_flag = True
                self.open_object_settings(object_id)
                self.scene.last_selected_object = object_id
                return True
        return False



    def unselect_objects(self):
        #print("Unselect objects")
        for model in self.scene.models:
            model.selected = False

        if self.status in ['edit', 'canceled']:
            self.close_object_settings()

    def add_camera_position(self, vec):
        self.view.add_camera_position(vec)

    def check_rotation_axis(self, event):
        if self.settings['toolButtons']['rotateButton']:
            if self.find_object_and_rotation_axis_by_color(event):
                self.update_scene()
                #self.view.update_scene()

    def copy_selected_objects(self):
        self.scene.copy_selected_objects()

    def paste_selected_objects(self):
        self.scene.paste_selected_objects()

    def delete_selected_objects(self):
        self.scene.delete_selected_models()
        self.view.close_object_settings_panel()
        self.actualize_extruder_set()

    def do_function(self):
        self.view.glWidget.do_button.press_button()

    def undo_function(self):
        self.view.glWidget.undo_button.press_button()



    def key_press_event(self, event):
        key = event.key()

        if self.status in ['generating', 'loading_gcode']:
            event.accept()
            return

        if key in [Qt.Key_Delete, Qt.Key_Backspace] and self.render_status == 'model_view' and not self.is_ctrl_pressed():
            self.delete_selected_objects()
            self.update_scene()
        elif key in [Qt.Key_C] and self.is_ctrl_pressed() and self.render_status == 'model_view':
            #print("Copy models")
            self.copy_selected_objects()
            self.update_scene()
        elif key in [Qt.Key_V] and self.is_ctrl_pressed() and self.render_status == 'model_view':
            #print("Paste models")
            self.paste_selected_objects()
            self.update_scene()
        elif key in [Qt.Key_Z] and self.is_ctrl_pressed() and self.render_status == 'model_view':
            #print("Undo pressed")
            self.unselect_tool_buttons()
            self.undo_function()
            #self.undo_button_pressed()
            self.update_scene()
        elif key in [Qt.Key_Y] and self.is_ctrl_pressed() and self.render_status == 'model_view':
            #print("Redo pressed")
            self.unselect_tool_buttons()
            self.do_function()
            #self.do_button_pressed()
            self.update_scene()
        elif key in [Qt.Key_R] and self.render_status == 'model_view' and not self.is_ctrl_pressed():
            #print("R pressed ")
            if self.view.glWidget.rotateTool.is_pressed():
                self.unselect_tool_buttons()
            else:
                self.unselect_tool_buttons()
                self.view.glWidget.rotateTool.press_button()
            self.update_scene()
        elif key in [Qt.Key_S] and self.render_status == 'model_view' and not self.is_ctrl_pressed():
            #print("S pressed ")
            if self.view.glWidget.scaleTool.is_pressed():
                self.unselect_tool_buttons()
            else:
                self.unselect_tool_buttons()
                self.view.glWidget.scaleTool.press_button()
            self.update_scene()
        elif key in [Qt.Key_A] and self.render_status == 'model_view':
            if self.is_ctrl_pressed() and not self.settings['toolButtons']['rotateButton'] and not self.settings['toolButtons']['scaleButton']:
                #print("A and ctrl pressed")
                self.select_all()
                self.update_scene()
            elif not self.is_ctrl_pressed() and not self.settings['toolButtons']['rotateButton'] and not self.settings['toolButtons']['scaleButton']:
                #print("just A pressed")
                self.unselect_tool_buttons()
                self.scene.automatic_models_position()
                self.update_scene()
        elif key in [Qt.Key_I] and self.render_status == 'model_view' and not self.settings['toolButtons']['rotateButton'] and not self.settings['toolButtons']['scaleButton']:
            if self.is_ctrl_pressed():
                #print("I and ctrl pressed ")
                self.invert_selection()
                self.update_scene()

        event.accept()


    def mouse_double_click(self, event):
        event.accept()


    def select_all(self):
        for m in self.scene.models:
            if m.isVisible:
                m.selected = True

    def invert_selection(self):
        for m in self.scene.models:
            if m.isVisible:
                m.selected = not m.selected

    '''
    def mouse_double_click(self, event):
        self.mouse_double_click_event_flag = True
        if self.render_status == 'model_view' and event.button() & QtCore.Qt.LeftButton:
            object_id = self.get_id_under_cursor(event)
            if object_id == 0 or self.is_some_tool_under_cursor(object_id):
                return
            else:
                self.open_object_settings(object_id)
    '''


    def mouse_press_event(self, event):
        #print("Mouse press event")
        self.clear_event_flag_status()
        self.mouse_press_event_flag = True

        newRayStart, newRayEnd = self.view.get_cursor_position(event)
        self.res_old = sceneData.intersection_ray_plane(newRayStart, newRayEnd)
        #Je stisknuto prave tlacitko?
        if event.button() & Qt.RightButton:
            self.set_camera_move_function()
        #Je stisknuto leve tlacitko?
        elif event.button() & Qt.LeftButton:
            #Je kurzor nad nejakym objektem?
            if self.render_status == 'model_view' and self.status in ['edit', 'canceled']:
                object_id = self.get_id_under_cursor(event)
                if object_id == 0 and self.settings['toolButtons']['supportButton']:
                    if self.scene.actual_support:
                        self.scene.save_actual_support()
                elif object_id==0:
                    self.set_camera_rotation_function()
                else:
                    #Je pod kurzorem nejaky tool?
                    if self.is_some_tool_under_cursor(object_id):
                        #print("pod kurzorem je Tool")
                        #self.unselect_objects()
                        self.tool_press_event_flag = True
                        self.tool = self.get_tool_by_id(object_id)
                        for t in self.tools:
                            if not t == self.tool:
                                t.unpress_button()
                            else:
                                self.tool.press_button()
                        #tool.activate_tool()

                    #Je pod kurzorem nejaky tool helper?
                    elif self.is_some_tool_helper_under_cursor(object_id):
                        #print("tool helper under cursor")
                        self.tool_helper_press_event_flag = True
                        #self.set_active_tool_helper_by_id(object_id)
                        self.prepare_tool(event)

                    elif self.is_object_already_selected(object_id) and self.is_ctrl_pressed():
                        #print("object already selected and ctrl pressed")
                        self.object_select_event_flag = True
                        self.cursor_over_object = True
                        self.unselect_object(object_id)
                    elif self.is_ctrl_pressed():
                        #print("ctrl pressed")
                        if self.settings['toolButtons']['rotateButton'] or self.settings['toolButtons']['scaleButton']:
                            self.unselect_objects()
                        self.select_object(object_id)
                        #disable object edit gui, its not possible for group
                        self.view.disable_object_settings_panel()
                        self.cursor_over_object = True
                    elif self.is_object_already_selected(object_id) and self.is_some_tool_active():
                        #print("object already selected and tool placeonface is on")
                        self.tool=self.get_active_tool()
                        self.prepare_tool(event)
                        self.cursor_over_object = True
                    elif self.is_object_already_selected(object_id):
                        #print("object already selected")
                        pass
                        self.cursor_over_object = True
                    else:
                        #print("else")
                        self.unselect_objects()
                        self.select_object(object_id)
                        self.cursor_over_object = True

                    #print("Aktualni tool je: " + self.tool)
                    self.tool = self.get_active_tool()
                    #Je objekt oznaceny?
                    '''
                    elif self.is_ctrl_pressed():
                        if self.is_object_already_selected(object_id):
                            self.unselect_object(object_id)
                        else:
                            self.select_object(object_id)
                    '''
                    #elif self.is_object_already_selected(object_id):


                    '''
                    elif self.unselect_objects_and_select_this_one(object_id):
                        print("Klikani na objekt")
                        #nastav funkci na provedeni toolu

                        self.tool = self.get_active_tool()
                        print("Aktualni tool je " + self.tool)

                        #TODO:add function get_active_tool(self) return class tool
                        #tool = self.get_toolsactive_tool()
                        #TODO:add function do(self) to class tool
                        self.prepare_tool(event)
                    else:
                        #select object
                        print("Else:")
                        self.unselect_objects()
                        self.select_object(object_id)
                    '''


            else:
                #print("Jiny status nez model_view")
                self.unselect_objects()
                self.set_camera_rotation_function()
        self.update_scene()
        #self.view.update_scene()
        event.accept()


    def is_some_tool_active(self):
        for tool in self.tools:
            if tool.is_pressed() and tool.tool_name=='placeonface':
                return True

        return False

    #def get_active_tool(self):
    #    for tool in self.tools:
    #        if tool.is_pressed():
    #            return tool.tool_name


    def prepare_tool(self, event):
        #print("prepare tool")
        if self.tool == 'rotate':
            for model in self.scene.models:
                if model.selected:
                    #newRayStart, newRayEnd = self.view.get_cursor_position(event)
                    #self.origin_rotation_point = sceneData.intersection_ray_plane(newRayStart, newRayEnd)
                    #self.res_old = self.origin_rotation_point
                    self.origin_rotation_point = numpy.array([1.,0.,0.])
                    self.origin_rotation_point += model.pos
                    self.origin_rotation_point[2] = 0.
                    self.res_old = self.origin_rotation_point
                    self.old_angle = model.rot[2]
            #self.view.glWidget.oldHitPoint = numpy.array([0., 0., 0.])
            #self.view.glWidget.hitPoint = numpy.array([0., 0., 0.])


        elif self.tool == 'placeonface':
            #print("inside placeonface")
            ray_start, ray_end = self.view.get_cursor_position(event)
            for model in self.scene.models:
                if model.selected:
                    self.view.glWidget.rayStart = ray_start
                    self.view.glWidget.rayDir = numpy.array(ray_end) - numpy.array(ray_start)
                    face = model.place_on_face(ray_start, ray_end)
                    if not face == []:
                        self.view.glWidget.v0 = face[0]
                        self.view.glWidget.v1 = face[1]
                        self.view.glWidget.v2 = face[2]
                        #print("Nalezen objekt " + str(model))
        elif self.tool == 'scale':
            ray_start, ray_end = self.view.get_cursor_position(event)

            for model in self.scene.models:
                if model.selected:
                    if model.is_multipart_model:
                        #pos = deepcopy(model.multipart_parent.pos)
                        #pos[2] = 0.
                        self.original_scale = deepcopy(model.multipart_parent.scale)
                    else:
                        #pos = deepcopy(model.pos)
                        #pos[2] = 0.
                        self.original_scale = deepcopy(model.scale)


    def mouse_move_event(self, event):
        #print("Mouse move event")
        self.mouse_move_event_flag = True
        dx = event.x() - self.last_pos.x()
        dy = event.y() - self.last_pos.y()
        #diff = numpy.linalg.norm(numpy.array([dx, dy]))

        if self.camera_move and self.mouse_press_event_flag:
            #print("camera move")
            camStart, camDir, camUp, camRight = self.view.get_camera_direction(event)
            right_move = -0.025*dx * camRight
            up_move = 0.025*dy * camUp

            move_vector = right_move + up_move
            self.add_camera_position(move_vector)

        elif self.camera_rotate and self.mouse_press_event_flag:
            #print("camera rotate")
            self.view.set_x_rotation(self.view.get_x_rotation() + 8 * dy)
            self.view.set_z_rotation(self.view.get_z_rotation() + 8 * dx)
            #camera_pos, direction, _, _ = self.view.get_camera_direction(event)
            #self.scene.camera_vector = direction - camera_pos
        #Check if some tool helper is pressed after that decide which tool is selected and
        #make some change, other way move
        elif self.tool_helper_press_event_flag:
            if self.tool == 'rotate':
                #print("rotate function")
                newRayStart, newRayEnd = self.view.get_cursor_position(event)
                res = sceneData.intersection_ray_plane(newRayStart, newRayEnd)
                if res is not None:
                    res_new = res - self.res_old
                    for model in self.scene.models:
                        if model.selected:
                            if model.is_multipart_model:
                                pos = deepcopy(model.multipart_parent.pos)
                            else:
                                pos = deepcopy(model.pos)
                            pos[2] = 0.

                            #New
                            new_vec = res - pos
                            #self.view.glWidget.hitPoint = deepcopy(new_vec)
                            new_vect_leng = numpy.linalg.norm(new_vec)
                            new_vec /= new_vect_leng

                            old_vec = self.res_old - pos
                            #self.view.glWidget.oldHitPoint = deepcopy(old_vec)
                            old_vec /= numpy.linalg.norm(old_vec)

                            cos_ang = numpy.dot(old_vec, new_vec)
                            cross = numpy.cross(old_vec, new_vec)

                            neg = numpy.dot(cross, numpy.array([0., 0., 1.]))
                            sin_ang = numpy.linalg.norm(cross) * numpy.sign(neg) * -1.

                            alpha = numpy.arctan2(sin_ang, cos_ang)

                            radius = model.max_bs

                            if radius < 2.5:
                                radius = 2.5
                            radius *=.7

                            if new_vect_leng >= radius:
                                if numpy.abs(alpha - numpy.pi) <= 0.05:
                                    alpha = numpy.pi

                                if model.is_multipart_model:
                                    model.set_rot(model.multipart_parent.rot[0], model.multipart_parent.rot[1], numpy.around(alpha, decimals=3), False, False, False)
                                else:
                                    model.set_rot(model.rot[0], model.rot[1], numpy.around(alpha, decimals=3), False, False, False)
                            else:
                                alpha_new = numpy.degrees(alpha) // 45.
                                if model.is_multipart_model:
                                    model.set_rot(model.multipart_parent.rot[0], model.multipart_parent.rot[1], alpha_new*(numpy.pi*.25), False, False, False)
                                else:
                                    model.set_rot(model.rot[0], model.rot[1], alpha_new*(numpy.pi*.25), False, False, False)

                            #self.view.update_object_settings(model.id)
                            self.view.update_rotate_widgets(model.id)
                            self.scene_was_changed()
            elif self.tool == 'scale':
                #print("scale function")
                ray_start, ray_end = self.view.get_cursor_position(event)
                # camera_pos, direction, _, _ = self.view.get_camera_direction(event)
                for model in self.scene.models:
                    if model.selected:
                        if model.is_multipart_model:
                            pos = deepcopy(model.multipart_parent.pos)
                            model_size_origin = deepcopy(model.multipart_parent.size_origin)
                        else:
                            pos = deepcopy(model.pos)
                            model_size_origin = deepcopy(model.size_origin)

                        pos[2] = 0.
                        new_scale_point = numpy.array(sceneData.intersection_ray_plane(ray_start, ray_end))
                        new_scale_vect = new_scale_point - pos

                        l = numpy.linalg.norm(new_scale_vect)
                        l -= .5

                        new_size = self.original_scale * model_size_origin
                        new_size[2] = 0.
                        new_size *= .5

                        origin_size = deepcopy(model_size_origin)
                        origin_size[2] = 0.
                        origin_size *= .5

                        if self.original_scale[0] == self.original_scale[1] == self.original_scale[2]:
                            #same proportion
                            v = l / numpy.linalg.norm(origin_size)
                            new_scale = numpy.array([v, v, v])
                        else:
                            v = l / numpy.linalg.norm(new_size)
                            new_scale = numpy.array([v*(self.original_scale)[0],
                                                v*(self.original_scale)[1],
                                                v*(self.original_scale)[2]])


                        new_scale = numpy.abs(new_scale)
                        model.set_scale_abs(new_scale[0], new_scale[1], new_scale[2])


                        #self.last_l = l

                        self.view.update_scale_widgets(model.id)
                        self.scene_was_changed()
        #Move function
        elif self.settings['toolButtons']['supportButton']:
            #print("support function")
            newRayStart, newRayEnd = self.view.get_cursor_position(event)
            res = sceneData.intersection_ray_plane(newRayStart, newRayEnd)
            if res is not None:
                self.scene.calculate_support(res)

        elif not self.tool_helper_press_event_flag \
                and self.mouse_press_event_flag \
                and self.cursor_over_object:
            #print("move function")
            newRayStart, newRayEnd = self.view.get_cursor_position(event)
            res = sceneData.intersection_ray_plane(newRayStart, newRayEnd)
            if res is not None:
                res_new = res - self.res_old
                for model in self.scene.models:
                    if model.selected:
                        model.set_move(res_new)
                        #self.view.update_object_settings(model.id)
                        self.view.update_position_widgets(model.id)
                        self.scene_was_changed()
                self.res_old = res

        else:
            #print("Mouse move event else vetev")
            if self.render_status == 'model_view':
                object_id = self.get_id_under_cursor(event)
                #TOOLs hover effect
                if object_id > 0:
                    #Je pod kurzorem nejaky tool?
                    for tool in self.tools:
                        if tool.id == object_id:
                            tool.mouse_is_over(True)
                            self.view.glWidget.setToolTip(tool.tool_tip)
                        else:
                            tool.mouse_is_over(False)

                    #if self.settings['toolButtons']['rotateButton']:
                    #    self.select_tool_helper_by_id(object_id)
                        #for tool_helper in self.get_tools_helpers_id(1,0):
                        #    if tool_helper == object_id:
                else:
                    #TODO:Disable tooltip
                    self.view.glWidget.setToolTip("")
                    for tool in self.tools:
                        tool.mouse_is_over(False)
        event.accept()


        self.last_pos = QPoint(event.pos())
        self.update_scene()
        #self.view.update_scene()

    def select_tool_helper(self, event):
        object_id = self.get_id_under_cursor(event)
        if object_id > 0:
            self.select_tool_helper_by_id(object_id)

    def select_tool_helper_by_id(self, object_id):
        for m in self.scene.models:
            if m.isVisible:
                if object_id == m.rotateZId:
                    m.rotationAxis = "Z"
                    m.scaleAxis = ""
                elif object_id == m.scaleXYZId:
                    m.scaleAxis = "XYZ"
                    m.rotationAxis = ""
                else:
                    m.rotationAxis = ""
                    m.scaleAxis = ""

    #def support_tool_button_pressed(self):
    #    self.tool = "support"

    def organize_button_pressed(self):
        self.scene.automatic_models_position()

    def get_active_tool(self):
        for tool in self.tools:
            if tool.pressed:
                #print("Tool name: " + str(tool.tool_name))
                return tool.tool_name
        return 'move'

    def mouse_release_event(self, event):
        models_list = []
        #print("Mouse releas event")
        self.mouse_release_event_flag = True
        self.set_camera_function_false()
        if self.tool in ['move', 'rotate', 'scale', 'placeonface']:
            self.old_angle = 0.0
            for model in self.scene.models:
                if model.selected:
                    if model.is_multipart_model:
                        model.multipart_parent.update_min_max()
                        if not self.tool == 'scale':
                            model.multipart_parent.recalc_bounding_sphere()
                        #TODO: add history for operations
                    else:
                        model.update_min_max()
                        if not self.tool == 'scale':
                            model.recalc_bounding_sphere()
                        models_list.append(model)
            if models_list and self.mouse_move_event_flag:
                self.scene.save_change(self.scene.models)
                #self.scene.save_change(models_list)

            self.update_wipe_tower()

        self.tool = ''
        self.res_old = numpy.array([0.,0.,0.])

        if event.button() & Qt.LeftButton and self.mouse_press_event_flag and\
                self.mouse_release_event_flag and self.mouse_move_event_flag == False and\
                self.object_select_event_flag==False and self.tool_press_event_flag == False:
            #print("Podminky splneny")
            self.clear_event_flag_status()
            self.unselect_objects()
        self.update_scene()
        event.accept()

        self.make_analyze()


    def make_analyze(self):
        if self.scene.was_changed() and self.settings['analyze']:
            self.scene.set_no_changes()
            self.analyzer.make_analyze(self.analyze_done, self.set_analyze_result_messages)


    def analyze_done(self):
        self.scene.set_no_changes()


    def open_object_settings(self, object_id):
        self.set_basic_settings()
        self.view.create_object_settings_menu(object_id)

    def close_object_settings(self):
        self.set_basic_settings()
        self.view.close_object_settings_panel()

    def set_printable(self, is_printable):
        self.scene.printable = is_printable
        if is_printable == False:
            #print("Disable genrate button")
            self.disable_generate_button()
        else:
            #print("Enable genrate button")
            self.enable_generate_button()

    def disable_generate_button(self):
        self.view.disable_generate_button()

    def enable_generate_button(self):
        self.view.enable_generate_button()

    def hit_objects(self, event):
        possible_hit = []
        nSelected = 0

        self.ray_start, self.ray_end = self.view.get_cursor_position(event)

        for model in self.scene.models:
            if model.intersection_ray_bounding_sphere(self.ray_start, self.ray_end):
                possible_hit.append(model)
                nSelected+=1
            else:
                #print("Tady bych to necekal")
                model.selected = False

        if not nSelected:
            return False

        #print("A tady taky ne")
        for model in possible_hit:
            if model.intersection_ray_model(self.ray_start, self.ray_end):
                model.selected = not model.selected
            else:
                model.selected = False

        return False

    def hit_first_object(self, event):
        possible_hit = []
        nSelected = 0
        self.ray_start, self.ray_end = self.view.get_cursor_position(event)
        self.scene.clear_selected_models()

        for model in self.scene.models:
            if model.intersection_ray_bounding_sphere(self.ray_start, self.ray_end):
                possible_hit.append(model)
                nSelected+=1

        if not nSelected:
            return False

        for model in possible_hit:
            if model.intersection_ray_model(self.ray_start, self.ray_end):
                model.selected = True
                return True

        return False

    def reset_transformation_on_object(self, object_id):
        object = self.get_object_by_id(object_id)
        object.reset_transformation()



#    @timing
    def get_id_under_cursor(self, event):
        return self.view.glWidget.get_id_under_cursor(event.x(), event.y())

    def hit_tool_button_by_color(self, event):
        find_id = self.get_id_under_cursor(event)
        if find_id == 0:
            return False
        id_list = [i.id for i in self.view.get_tool_buttons()]
        if find_id in id_list:
            for toolButton in self.view.get_tool_buttons():
                if find_id == toolButton.id:
                    toolButton.press_button()
                else:
                    toolButton.unpress_button()
        return False

    def hit_first_object_by_color(self, event, add=False):
        if not add:
            self.scene.clear_selected_models()
        find_id = self.get_id_under_cursor(event)
        if find_id == 0:
            return False
        for model in self.scene.models:
            if find_id in model.get_id():
                #print("Tady to je!!!")
                model.selected = not model.selected
                return True

    def reset_scene(self):
        self.scene.clear_scene()
        self.update_scene(True)
        self.is_model_loaded = False
        self.scene.is_wipe_tower_position_manual = False
        if self.is_multimaterial():
            self.actualize_extruder_set()
            self.add_wipe_tower()
        #self.view.update_scene(True)

    def clear_gui(self):
        self.view.reinit()

    def reset(self):
        #reset render mode
        self.scene_was_changed()
        self.set_model_edit_view()
        #reset gcode data
        self.clear_gcode()
        #reset gui
        self.clear_gui()
        self.reset_scene()
        self.analyze_result = {}

    def import_image(self, path):
        #TODO:Add importing of image(just plane with texture?)
        pass

    def undo_button_pressed(self):
        #print("Undo")
        self.clear_tool_button_states()
        self.scene.make_undo()
        self.update_scene()

    def do_button_pressed(self):
        #print("Do")
        self.clear_tool_button_states()
        self.scene.make_do()
        self.update_scene()

    def select_button_pressed(self):
        self.clear_tool_button_states()
        self.settings['toolButtons']['selectButton'] = True
        self.update_scene()
        #self.view.update_scene()

    def move_button_pressed(self):
        if self.settings['toolButtons']['moveButton']:
            self.settings['toolButtons']['moveButton'] = not(self.settings['toolButtons']['moveButton'])
        else:
            self.clear_tool_button_states()
            self.settings['toolButtons']['moveButton'] = True
        self.update_scene()
        #self.view.update_scene()

    def rotate_button_pressed(self):
        if self.settings['toolButtons']['rotateButton']:
            self.settings['toolButtons']['rotateButton'] = not(self.settings['toolButtons']['rotateButton'])
        else:
            self.clear_tool_button_states()
            self.settings['toolButtons']['rotateButton'] = True
        self.update_scene()
        self.unselect_objects()
        self.select_object(self.scene.last_selected_object)
        #self.view.update_scene()

    def support_button_pressed(self):
        if self.settings['toolButtons']['supportButton']:
            self.settings['toolButtons']['supportButton'] = not(self.settings['toolButtons']['supportButton'])
        else:
            self.clear_tool_button_states()
            self.settings['toolButtons']['supportButton'] = True
        self.update_scene()


    def scale_button_pressed(self):
        if self.settings['toolButtons']['scaleButton']:
            self.settings['toolButtons']['scaleButton'] = not(self.settings['toolButtons']['scaleButton'])
        else:
            self.clear_tool_button_states()
            self.settings['toolButtons']['scaleButton'] = True
        self.update_scene()
        self.unselect_objects()
        self.select_object(self.scene.last_selected_object)
        #self.view.update_scene()

    def place_on_face_button_pressed(self):
        #TODO:Add new tool
        pass

    def clear_tool_button_states(self):
        self.settings['toolButtons'] = {a: False for a in self.settings['toolButtons']}

    def slicing_message(self, string_in):
        #Translation of messages from slicing engine
        translation_table = {'Generating perimeters': self.tr('Generating perimeters'),
                             'Processing triangulated mesh': self.tr('Processing triangulated mesh'),
                             'Infilling layers': self.tr('Infilling layers'),
                             'Preparing infill': self.tr('Preparing infill'),
                             'Generating skirt': self.tr('Generating skirt'),
                             'Exporting G-code to': self.tr('Exporting G-code to'),
                             'Done. Process took': self.tr('Done. Process took')
                             }

        string_in_str = str(string_in)
        if string_in_str in translation_table:
            string_out = translation_table[string_in_str]
        else:
            string_out = string_in

        self.show_message_on_status_bar(string_out)


    def show_message_on_status_bar(self, string):
        self.view.statusBar().showMessage(string)

    def open_clear_scene_and_load_gcode_file(self):
        ret = self.view.show_clear_scene_and_load_gcode_file_dialog()
        if ret == QMessageBox.Yes:
            self.scene.clear_scene()
            return True
        elif ret == QMessageBox.No:
            return False

    def open_cancel_gcode_preview_dialog(self):
        ret = self.view.show_open_cancel_gcode_preview_dialog()
        if ret == QMessageBox.Yes:
            self.status = 'edit'
            self.set_model_edit_view()
            return True
        elif ret == QMessageBox.No:
            return False


    def get_url_from_local_fileid(self, localFileID):
        if not self.app_config.system_platform in ["Darwin"]:
            return ""
        else:
            import objc
            import CoreFoundation as CF

            relCFURL = CF.CFURLCreateWithFileSystemPath(
                CF.kCFAllocatorDefault,
                localFileID,
                CF.kCFURLPOSIXPathStyle,
                False  # is directory
            )
            absCFURL = CF.CFURLCreateFilePathURL(
                CF.kCFAllocatorDefault,
                relCFURL,
                objc.NULL
            )
            url_tmp = str(absCFURL[0])
            if url_tmp.startswith('file://'):
                url = url_tmp[7:]
            else:
                url = url_tmp
            url = url.replace('%20', ' ')

            return url

    def open_ask_multipart_model_dialog(self):
        ret = self.view.show_ask_multipart_model_dialog()
        if ret == QMessageBox.Yes:
            self.cancel_generation()
            return True
        elif ret == QMessageBox.No:
            return False

    def open_files(self, list_of_urls_tmp):
        list_of_urls = []
        list_of_urls_tmp2 = []
        if self.app_config.system_platform in ["Darwin"]:
            for url in list_of_urls_tmp:
                if url.startswith('/.file/id='):
                    list_of_urls_tmp2.append(self.get_url_from_local_fileid(url))
                else:
                    list_of_urls_tmp2.append(url)
        else:
            list_of_urls_tmp2 = list_of_urls_tmp

        list_of_urls = sorted(list_of_urls_tmp2)

        extensions_lst = []
        for url in list_of_urls:
            urlSplited = url.split('.')
            if len(urlSplited) == 2:
                fileEnd = urlSplited[1]
            elif len(urlSplited) > 2:
                fileEnd = urlSplited[-1]
            else:
                fileEnd = ''
            extensions_lst.append(fileEnd.lower())

        extensions_set = set(extensions_lst)
        if len(extensions_set) == 1:
            if list(extensions_set)[0] in ['stl']:
                #show message of multipart model
                if self.open_ask_multipart_model_dialog():
                    #load together
                    self.load_multipart_model(list_of_urls)
                else:
                    #load separately
                    for url in list_of_urls:
                        self.import_model(url)
            self.show_warning_if_used_materials_are_not_compatible()
        else:
            self.view.statusBar().showMessage("Some files mismatch")

        self.actualize_extruder_set()

    def find_network_printers(self):
        pass


    def open_file(self, url):
        '''
        function for resolve which file type will be loaded
        '''
        #print("Urls type: " + str(type(url)))

        if self.status in ['generating']:
            if not self.open_cancel_generating_dialog():
                return
        elif self.status in ['loading_gcode']:
            if not self.open_cancel_gcode_reading_dialog():
                return
        elif self.status in ['generated']:
            if not self.open_cancel_gcode_preview_dialog():
                return


        if self.app_config.system_platform in ["Darwin"]:
            if url.startswith('/.file/id='):
                url = self.get_url_from_local_fileid(url)



        urlSplited = url.split('.')
        if len(urlSplited)==2:
            fileEnd = urlSplited[1]
        elif len(urlSplited)>2:
            fileEnd = urlSplited[-1]
        else:
            fileEnd=''

        if fileEnd in ['stl', 'STL', 'Stl']:
            #print('import model')
            self.import_model(url)
        elif fileEnd in ['prusa', 'PRUSA']:
            #print('open project')

            self.open_project_file(url)
        elif fileEnd in ['jpeg', 'jpg', 'png', 'bmp']:
            #print('import image')
            self.import_image(url)
        elif fileEnd in ['gcode']:
            if self.is_something_to_save():
                if not self.open_clear_scene_and_load_gcode_file():
                    return
            self.read_gcode(url)

        self.actualize_extruder_set()


