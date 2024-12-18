"""
Class for the custom spectrometer
When have time - think about how to make use of inheritence and make the camera a separate object!
MS: How about making the camera the base class and making the spectrometer inherit from the camera?
"""
import matplotlib.pylab as plt
import matplotlib.cm as cm
import numpy as np
import copy
import time

from pypylon import pylon

from IPython import display
from matplotlib.ticker import FormatStrFormatter

cmap = copy.copy(cm.get_cmap('binary'))
cmap_sat  = copy.copy(cm.get_cmap('binary'))
cmap_sat.set_over('red')

wait = 5e-2

def active_sleep(t):
    target_time = time.perf_counter() + t
    while time.perf_counter() < target_time:
        pass

class Spectrometer():
    def __init__(s):
        camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        s.camera = camera

        s.img_list = list()
        #use the img_list defined in this scope
        class SpectraImageEventHandler(pylon.ImageEventHandler):
            def OnImageGrabbed(self, camera, grabResult):
                s.img_list.append(grabResult.Array)

        s.SpectraImageEventHandler = SpectraImageEventHandler
        s.measurement_mode()

    def setup_mode(s):
        s.camera.Close()
        s.camera.Open()

    def measurement_mode(s):
        SpectraImageEventHandler = s.SpectraImageEventHandler
        camera = s.camera
        camera.RegisterConfiguration(pylon.SoftwareTriggerConfiguration(), pylon.RegistrationMode_ReplaceAll, pylon.Cleanup_Delete)
        camera.RegisterImageEventHandler(SpectraImageEventHandler(), pylon.RegistrationMode_Append, pylon.Cleanup_Delete)
        camera.StartGrabbing(pylon.GrabStrategy_OneByOne, pylon.GrabLoop_ProvidedByInstantCamera)
        
    def clear_img_list(s):
        s.img_list = list()

    def add_img(s, wait):
        camera = s.camera
        if camera.WaitForFrameTriggerReady(1000000000, pylon.TimeoutHandling_ThrowException):
            camera.ExecuteSoftwareTrigger()
        active_sleep(wait)

    def take_imgs(s, N, wait=wait):
        s.clear_img_list()
        for i in range(N):
            s.add_img(wait)
        return s.img_list

    def take_img(s, wait=wait):
        return s.take_imgs(2, wait=wait)[-1]

    def show_img(s, figsize=(12, 3), flag_sat = False):
        fig, ax = plt.subplots(figsize=figsize)
        img = s.take_img()
        if flag_sat:
            plt.imshow(img, cmap=cmap_sat, vmax=254.99)
        else:
            plt.imshow(img, cmap=cmap, vmax=255)
        plt.colorbar()
        plt.grid(alpha=0.2)

    def show_spec(s, figsize=(12, 3)):
        fig, ax = plt.subplots(figsize=figsize)
        plt.plot(s.take_spec(), color="k")
        plt.grid(alpha=0.2)

    def show_video(s, figsize=(12, 3)):
        fig, ax = plt.subplots(figsize=figsize)

        try:
            while True:
                fig.clf()
                img = s.take_img()
                plt.imshow(img, cmap=cmap, vmax=255)
                plt.colorbar()
                plt.grid(alpha=0.2)
                display.clear_output(wait=True)
                display.display(plt.gcf())
        
        except:
            display.clear_output(wait=True)
            print("Stopping Video - hope you enjoyed it :)")
            
    def show_video_histogram(s, figsize=(10, 10)):
        
        fig, ax = plt.subplots(figsize=figsize)

        try:
            while True:
                fig.clf()
                img = cam.take_img()
                plt.hist(img.flatten(), range = (0,255), bins = 85);
                plt.grid(alpha=0.2)
                display.clear_output(wait=True)
                display.display(plt.gcf())

        except:
            display.clear_output(wait=True)
            print("Stopping Video - hope you enjoyed it :)")
            
    def show_video_with_spatial_profiles(s, figsize=(10, 10)):
        fig, ax = plt.subplots(figsize=figsize)
        
        try:
            while True:
                fig.clf();
                cam_img = s.take_img();

                ncol, nrow = 5, 4
                fig = plt.figure(figsize=(ncol + 0.3, nrow + 0.3), dpi = 150);#, facecolor='white')
                spec = fig.add_gridspec(nrow, ncol);

                ax0 = fig.add_subplot(spec[:(nrow-1), :(ncol-1)]);
                ax0.imshow(cam_img, aspect = 'equal', cmap = cm.Greys, vmin =0, vmax = 255);
                ax0.set_xticks([]);
                ax0.set_yticks([]);

                ax10 = fig.add_subplot(spec[nrow-1, :(ncol-1)]);
                ax10.plot(cam_img.mean(axis = 0));
                ax10.set_xticks(ticks = np.linspace(0, 4024, 10));
                ax10.set_xticklabels([]);
                ax10.set_yticks(ticks = np.linspace(0, 255, 5));
                ax10.set_yticklabels([]);
                ax11.set_ylim(0,255);
                ax11.set_xlim(0,4024);
                ax10.grid();

                plt.xlim(0, 4024);
                ax11 = fig.add_subplot(spec[:(nrow-1), ncol-1]);
                ax11.plot(cam_img.mean(axis = 1), range(cam_img.shape[0]));
                ax11.set_yticks(ticks = np.linspace(0, 3036, 10));
                ax11.set_yticklabels([]);
                ax11.set_xticks(ticks = np.linspace(0, 255, 5));
                ax11.set_xticklabels([]);
                ax11.set_xlim(0,255);
                ax11.set_ylim(0,3036);
                ax11.invert_xaxis();
                ax11.invert_yaxis();
                ax11.grid();

                display.clear_output(wait=True);
                display.display(plt.gcf());

        except:
            display.clear_output(wait=True);
            print("Stopping Video - hope you enjoyed it :)")

    def show_spec_video(s, figsize=(12, 5), Navg=5):
        spec = s.take_spec(Navg=Navg)
        ymax = np.max(spec)*1.3
        fig, ax = plt.subplots(figsize=figsize)
        try:
            while True:
                fig.clf()
                ax = plt.gca()
                ax.yaxis.set_major_formatter(FormatStrFormatter('%.0f'))
                spec = s.take_spec(Navg=Navg)
                plt.plot(spec)
                plt.grid(alpha=0.2)
                plt.ylim(0, ymax)
                display.clear_output(wait=True)
                display.display(plt.gcf())

        except:
            display.clear_output(wait=True)
            print("Stopping Video - hope you enjoyed it :)")

    def get_specs(s):
        img_list = s.img_list
        specs = np.array([np.mean(img, axis=0) for img in img_list])
        return specs

    def take_specs(s, N, wait=wait):
        s.take_imgs(N, wait=wait)
        return s.get_specs()

    def take_spec(s, Navg=2, wait=10e-3):
        return np.mean(s.take_specs(Navg, wait=wait), axis=0)

    @property
    def exposure_time(s):
        return s.camera.ExposureTime.GetValue()

    @exposure_time.setter
    def exposure_time(s, value):
        s.camera.ExposureTime.SetValue(value)

    @property
    def width(s):
        return s.camera.Width.GetValue()

    @width.setter
    def width(s, value):
        value = round(value/16)*16
        s.setup_mode()
        s.camera.Width.SetValue(value)
        s.measurement_mode()

    @property
    def height(s):
        return s.camera.Height.GetValue()

    @height.setter
    def height(s, value):
        s.setup_mode()
        s.camera.Height.SetValue(value)
        s.measurement_mode()

    @property
    def offset_x(s):
        return s.camera.OffsetX.GetValue()

    @offset_x.setter
    def offset_x(s, value):
        value = round(value/16)*16
        return s.camera.OffsetX.SetValue(value)

    @property
    def offset_y(s):
        return s.camera.OffsetY.GetValue()

    @offset_y.setter
    def offset_y(s, value):
        return s.camera.OffsetY.SetValue(value)

    def max_bounds(s):
        s.offset_x = 0
        s.offset_y = 0
        s.width = 4016
        s.height = 3036
