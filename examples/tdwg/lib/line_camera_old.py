"""
I am keeping this around so that I can easy port over the vimba functionalities if I desire at a later point...
"""


import matplotlib.pyplot as plt
import numpy as np

from pylablib.devices import BitFlow
from vimba import *
import astropy.units as u
from astropy.visualization import quantity_support
quantity_support()

import ipywidgets as widgets
from IPython.display import display
from IPython import get_ipython
from matplotlib.animation import FuncAnimation
from ipywidgets import Button

import time
import warnings

default_cmap = "hot" #this can be changed at will!
cam_left_cut_ind = 10 #this is the number of pixels to cut off the left side of the image

class LineCamera():
    def __init__(self,
                 calibration_dict = dict(
                     xaxis_shift = 0,
                     cam_mag = 5.555
                 ),  
                 online=True):
        """
        This init turns on the frame grabber
        
        camera_mag: Camera Magnification
        """
        if online:
            self.openFrameGrabber()
            self.fg.start_acquisition()
        self.vimba_flag = False #this flag tells you whether vimba is open
        self.mask_flag = False #sets a mask for the images that are taken
        self.mask = None #Just throw it doesn't throw an error if there isn't any?
        self.load_calibration(calibration_dict)

    def load_calibration(self, calibration_dict):
        self.cam_mag = calibration_dict["cam_mag"]
        self.xaxis_shift = calibration_dict["xaxis_shift"]
        x_axis = self.get_xaxis()
        self.x_axis = x_axis
        
    def openFrameGrabber(self):
        fg = BitFlow.BitFlow.BitFlowFrameGrabber(bitflow_camfile = 'C:\BitFlow SDK 6.5\Config\Axn\AlliedVision-Goldeye-CL-033.bfml')
        fg._camed.set_mode_parameters(bpp ='14') # set bit depth to 14 pixels
        self.fg = fg
        
    def closeFrameGrabber(self):
        self.fg.stop_acquisition()
        self.fg.close()
    
    def openVimba(self):
        """
        This code will open vimba, allowing you to change the settings of the camera
        Note that it takes forever to run, so by default the code will in initialization open vimba
        """
        vimba = Vimba.get_instance()
        vimba = vimba.__enter__()

        cams = vimba.get_all_cameras()
        cam = cams[0]
        cam.__enter__()
        
        self.vimba = vimba
        self.cam = cam
        self.vimba_flag = True
        
    def closeVimba(self):
        self.cam.__exit__(exc_type=None, exc_value=None, exc_traceback=None)
        self.vimba.__exit__(None, None, None)
        
    def trigger_on(self):
        self.cam.TriggerSource.set("Line1")
        
    def trigger_off(self):
        self.cam.TriggerSource.set("Freerun") #FIGURE THIS OUT
        
    def print_settings(self):
        if self.vimba_flag:
            print("Vimba settings:")
            cam = self.cam
            print(f"   Exposure time: {cam.ExposureTime.get()}")
            print(f"   Binning Vertical: {cam.BinningVertical.get()}")
            print(f"   ROI height: {cam.Height.get()}")
            print(f"   ROI OffsetY: {cam.OffsetY.get()}")

            print(f"   Trigger Source: {cam.TriggerSource.get().as_tuple()}")       
            
        print("Frame Grabber settings:")
        print(f"   ROI settings {self.fg.get_roi()}")
    
    def set_OffsetY(self, OffsetY):
        self.cam.OffsetY.set(OffsetY)
    
    def set_ROI(self, ROIheight):
        """
        This code sets the ROI. For vimba it will set it too, if it is enabled
        """
        self.closeFrameGrabber()
        
        if self.vimba_flag:
            self.cam.Height.set(ROIheight)
            self.closeVimba()
            print("Have closed Vimba so framegrabber ROI settings are updated")
            self.vimba_flag = False
        else:
            print("Vimba is not turned on - so only setting the ROI of the frame-grabber")
            
        #my understanding is that opening the frameGrabber cannot happen when vimba is turned on!
        self.openFrameGrabber()
        self.fg.set_grabber_roi(hstart=0, hend=640, vstart=0, vend=ROIheight)
        self.fg.start_acquisition()

    def set_default_ROI(self):
        self.set_OffsetY(0)
        self.set_ROI(self.get_resY())
        
    def set_exposure_time(self, exposure_time):
        if exposure_time < 1e6:
            self.cam.ExposureTime.set(exposure_time)
        else:
            print(f'Exposure time should not be set over 1000000. Requested exposure time: {exposure_time}')
        
    def set_mask(self, mask):
        """
        This sets a software mask over the image that is taken by the camera
        The purpose of this is to increase the SNR
        an example mask would be mask = np.arange(10, 30) -> only takes a mask in the height dimensions
        """
        self.mask_flag = True
        self.mask = mask
        
    def turn_off_mask(self):
        """
        Run this, if you no longer want to "mask" the image output
        """
        self.mask_flag = False

    def set_mask_range(self, left_ind, right_ind):
        """
        Mostly a convenience function to set a mask over a range of pixels
        """
        mask = np.arange(left_ind, right_ind)
        self.set_mask(mask)

    def find_ind_slab(self):
        """
        This function finds the index of the slab in the image
        """
        img = self.get_image()
        vertical_trace = img.mean(axis=1)
        diff_vertical_trace = np.diff(vertical_trace)
        ind_slab = np.argmax(diff_vertical_trace)+1
        return ind_slab

    def auto_set_mask(self, mask_range):
        self.set_mask_range(0, 512)
        ind_slab = self.find_ind_slab()

        if mask_range % 2: #if mask_range is odd
            single_side = (mask_range-1)//2
            self.set_mask_range(ind_slab-single_side, ind_slab+single_side+1)
        else:
            single_side = mask_range//2
            self.set_mask_range(ind_slab-single_side, ind_slab+single_side)

    def get_image(self, saturation_warning = True):
        fg_out = None
        while fg_out == None:
            self.fg.wait_for_frame('now')  # wait for the next available frame
            fg_out = self.fg.read_newest_image(return_info=True)
        # return info contains the frame index, which allows us to tell whether frames were skipped
        img, info = fg_out
        
        if self.mask_flag:
            img = img[self.mask]
        
        MAXVAL = 15000 #here 15000 was measured to be a decent cutoff because saturation on camera apparently means output values have fluctuations when camera is saturated see notes on 2023-01-23
        #now check for getting out of range carefully.
        if img.max() > MAXVAL and saturation_warning: 
            #then probably good to check how many frames are exceeding the limits?
            Npixels = np.sum(img > MAXVAL)
            warn_msg = f"There is saturation on camera!\n{Npixels} pixels are saturated!"
            warnings.warn(warn_msg)
            
        img = img[:, cam_left_cut_ind:]
        img = img[:, ::-1]
        return img        

    def get_output(self, saturation_warning = True):
        img = self.get_image(saturation_warning=saturation_warning)
        return img.mean(axis=0)
    
    def get_exposure_time(self):
        return self.cam.ExposureTime.get()
    
    def get_resX(self):
        return 640 - cam_left_cut_ind
    
    def get_resY(self):
        return 512
    
    def get_pixelpitch(self):
        #returns pixel pitch in METERS
        return 15*u.um
    
    def get_xaxis(self):
        return self._get_xaxis(self.cam_mag) - self.xaxis_shift
    
    def _get_xaxis(self, magnification):
        #returns a magnified xaxis in units on mm (with units package)
        #The reason that I am keeping a private version of the function is because this function is something quite useful outside of the object
        resx = self.get_resX()
        x_axis = (np.arange(resx) - resx/2)*self.get_pixelpitch()
        x_axis_rescaled = x_axis/magnification
        return x_axis_rescaled.to(u.mm)
    
    def get_yaxis(self):
        #returns a magnified yaxis in units on mm (with units package)
        if self.mask_flag: resy = len(self.mask)
        else: resy = self.get_resY()
        y_axis = (np.arange(resy) - resy/2)*self.get_pixelpitch()
        y_axis_rescaled = y_axis/self.cam_mag
        return y_axis_rescaled.to(u.mm)

    def show_image(self, figsize=(6, 2), vmax=None, cmap=default_cmap):
        cam_img = self.get_image()

        if vmax is None:
            vmax = cam_img.max()

        xaxis = self.get_xaxis().value
        yaxis = self.get_yaxis().value
        Ny = np.shape(cam_img)[0]
        
        fig = plt.figure(figsize=figsize)
        im = plt.imshow(cam_img, cmap=cmap, aspect="auto",
                        extent=[xaxis.min(), xaxis.max(), yaxis.min(), yaxis.max()], vmax=vmax)
        self.im = im
        self.fig = fig
        plt.colorbar()
        plt.xlabel("mm")
        plt.ylabel("mm")
        plt.grid(alpha=0.7)

        fig.canvas.header_visible = False
        fig.canvas.footer_visible = False
        plt.tight_layout()
    
    def show_output(self, figsize=(6, 2), ymax=None, color="r", saturation_warning = True):
        output = self.get_output(saturation_warning=saturation_warning)

        if ymax is None:
            ymax = output.max()
            
        xaxis = self.get_xaxis()
        
        fig, ax = plt.subplots(1,1, figsize=figsize)
        self.ax = ax
        self.fig = fig
        plt.plot(xaxis, output, color=color)
        #xlable is done automatically from the units library!

        fig.canvas.header_visible = False
        fig.canvas.footer_visible = False

        plt.ylim(top=ymax*1.1)
        plt.grid(alpha=0.2)
        plt.tight_layout()
        
    #### The following code is for video related stuff #####

    def start_image_video(self, figsize=(6, 4), cmap=default_cmap):
        set_matplotlib_widget()
        self.image_video_running = True

        # Define a function that updates the plot
        def update_plot(_):
            if self.image_video_running:
                cam_img = self.get_image(saturation_warning=False)
                im.set_data(cam_img)
                im.set_clim(vmax=vmax_slider.value)
            else:
                # Stop the animation if the global flag is set to False
                ani.event_source.stop()

        xaxis = self.get_xaxis().value
        yaxis = self.get_yaxis().value

        cam_img = self.get_image(saturation_warning=False)
        Ny = np.shape(cam_img)[0]

        fig, ax = plt.subplots(figsize=figsize)
        im = plt.imshow(cam_img, cmap=cmap, aspect="auto",
                        extent=[xaxis.min(), xaxis.max(), yaxis.min(), yaxis.max()])
        plt.colorbar(im, ax=ax)

        plt.xlabel("mm")
        plt.ylabel("mm")
        plt.grid(alpha=0.7)

        fig.canvas.header_visible = False
        fig.canvas.footer_visible = False
        plt.tight_layout()

        # Animation object
        ani = FuncAnimation(fig, update_plot, interval=100, blit=False)

        # Create a slider widget to control vmax value
        vmax_slider = widgets.FloatSlider(
            value=np.max(cam_img),
            min=0,
            max=16000,
            step=100,
            description='vmax:',
            continuous_update=True,
            orientation='horizontal',
            readout=True,
            readout_format='.1f',
        )

        # Display the slider
        display(vmax_slider)

        # Now create a FloatText widget to control exposure_time
        # Only run this if vimba is currently turned on
        if self.vimba_flag:
            exposure_time_input = widgets.FloatText(
                value=self.get_exposure_time(),
                description='Exposure time:',
                continuous_update=False
            )

            # Display the input field
            display(exposure_time_input)

            # Define a function to update exposure time when the input value changes
            def on_exposure_time_change(change):
                new_exposure_time = change['new']
                self.set_exposure_time(new_exposure_time)

            # Attach the callback function to the FloatText widget
            exposure_time_input.observe(on_exposure_time_change, names='value')

        stop_button = Button(description='Stop Video')

        # Define a function to call self.stop_image_video when the button is clicked
        def on_stop_button_click(_):
            self.stop_image_video()

        # Attach the callback function to the Button widget
        stop_button.on_click(on_stop_button_click)

        # Display the button
        display(stop_button)
    
    def stop_image_video(self):
        self.image_video_running = False
        set_matplotlib_inline()
        
    def start_output_video(self, figsize=(6, 2), color="tab:red", ymax=None, saturation_warning=True):
        set_matplotlib_widget()
        self.output_video_running = True

        # Define a function that updates the plot
        def update_plot(_):
            if self.output_video_running:
                output = self.get_output(saturation_warning=saturation_warning)
                ax.lines[0].set_ydata(output)
            else:
                # Stop the animation if the global flag is set to False
                ani.event_source.stop()

        output = self.get_output(saturation_warning=saturation_warning)

        if ymax is None:
            ymax = output.max()

        xaxis = self.get_xaxis()

        fig, ax = plt.subplots(1,1, figsize=figsize)
        plt.plot(xaxis, output, color=color)

        fig.canvas.header_visible = False
        fig.canvas.footer_visible = False

        # Create FloatText widgets for ymin and ymax
        ymin_input = widgets.FloatText(
            value = round(output.min()),
            description = 'ymin:',
            continuous_update = True
        )
        ymax_input = widgets.FloatText(
            value = round(1.1*ymax),
            description = 'ymax:',
            continuous_update = True
        )

        # Display the input fields
        display(ymin_input)
        display(ymax_input)

        def update_ylim(*args):
            plt.ylim(bottom=ymin_input.value, top=ymax_input.value)

        ymin_input.observe(update_ylim, 'value')
        ymax_input.observe(update_ylim, 'value')

        plt.ylim(bottom=ymin_input.value, top=ymax_input.value)
        plt.grid(alpha=0.2)
        plt.tight_layout()

        # Animation object
        ani = FuncAnimation(fig, update_plot, interval=100, blit=False)

        stop_button = Button(description='Stop Video')

        # Define a function to call self.stop_image_video when the button is clicked
        def on_stop_button_click(_):
            self.stop_output_video()

        # Attach the callback function to the Button widget
        stop_button.on_click(on_stop_button_click)

        # Display the button
        display(stop_button)

    def stop_output_video(self):
        self.output_video_running = False
        set_matplotlib_inline()

######## general functions for toggling behavoir of matplotlib in jupyter lab ############
def set_matplotlib_inline():
    ipython = get_ipython()
    if ipython is not None:
        ipython.run_line_magic("matplotlib", "inline")
        
def set_matplotlib_widget():
    ipython = get_ipython()
    if ipython is not None:
        ipython.run_line_magic("matplotlib", "widget")