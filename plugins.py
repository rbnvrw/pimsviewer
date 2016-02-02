from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from pimsviewer.viewer import Plugin
from pimsviewer.display import DisplayMPL


class ViewerPipeline(Plugin):
    """Base class for viewing the result of image processing inside the Viewer.

    The ViewerPipeline class connects an image filter (or another function) to
    the Viewer. The Viewer returns a reader object that has the function applied
    with parameters set inside the Viewer.

    Parameters
    ----------
    pipeline_func : function
        Function that processes the image. It should not change the image shape.
    name : string
        Name of pipeline. This is displayed as the window title.
    height, width : int
        Size of plugin window in pixels. Note that Qt will automatically resize
        a window to fit components. So if you're adding rows of components, you
        can leave `height = 0` and just let Qt determine the final height.
    dock : {bottom, top, left, right}
        Default docking area

    Examples
    --------
    >>> import numpy as np
    >>> from pims.viewer import Viewer, ViewerPipeline, Slider
    >>>
    >>> def add_noise(img, noise_level):
    >>>     return img + np.random.random(img.shape) * noise_level
    >>>
    >>> image_reader = np.zeros((1, 512, 512), dtype=np.uint8)
    >>>
    >>> AddNoise = ViewerPipeline(add_noise) + Slider('noise_level', 0, 100, 0)
    >>> viewer = Viewer(image_reader)
    >>> viewer += AddNoise
    >>> original, noise_added = viewer.show()

    Notes
    -----
    ViewerPipeline was partly based on `skimage.viewer.plugins.Plugin`
    """
    # the class keeps a list of its instances
    instances = []
    def __init__(self, pipeline_func, name=None, height=0, width=400,
                 dock='bottom'):
        self.pipeline_func = pipeline_func

        if name is None:
            self.name = pipeline_func.__name__
        else:
            self.name = name

        super(ViewerPipeline, self).__init__(height, width, dock)

        ViewerPipeline.instances.append(self)

    def attach(self, viewer):
        """Attach the pipeline to an ImageViewer.

        Note that the ImageViewer will automatically call this method when the
        plugin is added to the ImageViewer. For example:

            viewer += Plugin(pipeline_func)

        Also note that `attach` automatically calls the filter function so that
        the image matches the filtered value specified by attached widgets.
        """
        super(ViewerPipeline, self).attach(viewer)
        self.viewer.plugins.append(self)
        self.viewer._readers += [None]
        self.reader_index = len(self.viewer._readers) - 1
        self.viewer._readers[self.reader_index] = self.viewer._readers[self.reader_index - 1]

        self.process()

    def _process(self):
        kwargs = dict([(name, self._get_value(a))
                       for name, a in self.keyword_arguments.items()])
        self.viewer._readers[self.reader_index] = \
            self.pipeline_func(self.viewer._readers[self.reader_index - 1],
                               *self.arguments, **kwargs)

    def process(self, *widget_arg):
        """Send the changed pipeline function to the Viewer. """
        # `widget_arg` is passed by the active widget but is unused since all
        # filter arguments are pulled directly from attached the widgets.
        to_process = [None] * (len(self.viewer._readers) - self.reader_index)
        for plugin in self.viewer.plugins:
            try:
                if plugin.reader_index >= self.reader_index:
                    to_process[plugin.reader_index - self.reader_index] = plugin
            except AttributeError:
                pass  # no pipeline_index
        for plugin in to_process:
            plugin._process()
        self.viewer.update_image()

    def close(self):
        """Close the plugin and clean up."""
        if self in self.viewer.plugins:
            self.viewer.plugins.remove(self)

        # delete the pipeline
        if self.reader_index is not None:
            del self.viewer._readers[self.reader_index]
        # decrease pipeline_index for the other pipelines
        for plugin in self.viewer.plugins:
            try:
                if plugin.reader_index > self.reader_index:
                    plugin.reader_index -= 1
            except AttributeError:
                pass  # no pipeline_index

        self.viewer.update_view()

        super(ViewerPipeline, self).close()


class ViewerPlotting(Plugin):
    def __init__(self, plot_func, name=None, height=0, width=400,
                 dock='bottom'):
        if name is None:
            self.name = plot_func.__name__
        else:
            self.name = name

        super(ViewerPlotting, self).__init__(height, width, dock)

        self.artist = None
        self.plot_func = plot_func

    def attach(self, viewer):
        super(ViewerPlotting, self).attach(viewer)

        if type(viewer.renderer) is not DisplayMPL:
            viewer.update_display(DisplayMPL)

        self.fig = viewer.renderer.fig
        self.ax = viewer.renderer.ax
        self.canvas = viewer.renderer.widget

        self.viewer.image_changed.connect(self.process)

        self.process()

    def process(self, *widget_arg):
        kwargs = dict([(name, self._get_value(a))
                       for name, a in self.keyword_arguments.items()])
        if self.artist is not None:
            remove_artists(self.artist)
        self.artist = self.plot_func(self.viewer.image, *self.arguments,
                                     ax=self.ax, **kwargs)
        self.canvas.draw_idle()


class ViewerAnnotate(Plugin):
    name = 'Annotate'

    def __init__(self, features, cropped=False):
        super(ViewerAnnotate, self).__init__(dock=False)
        self.artist = None
        self.features = features
        self.cropped = cropped

    def attach(self, viewer):
        super(ViewerAnnotate, self).attach(viewer)

        if type(viewer.renderer) is not DisplayMPL:
            viewer.update_display(DisplayMPL)

        self.fig = viewer.renderer.fig
        self.ax = viewer.renderer.ax
        self.canvas = viewer.renderer.widget

        self.viewer.image_changed.connect(self.process)

        self.process()

    def process(self, *widget_arg):
        frame_no = self.viewer.index['t']
        _plot_style = dict(markersize=15, markeredgewidth=2,
                           markerfacecolor='none', markeredgecolor='r',
                           marker='o', linestyle='none')
        f_frame = self.features[self.features['frame'] == frame_no]
        if self.cropped:
            self.ax.set_xlim(int(f_frame['x'].min()) - 15,
                             int(f_frame['x'].max()) + 15)
            self.ax.set_ylim(int(f_frame['y'].max()) + 15,
                             int(f_frame['y'].min()) - 15)
        if self.artist is not None:
            remove_artists(self.artist)
        if len(f_frame) == 0:
            self.artist = None
        else:
            self.artist = self.ax.plot(f_frame['x'], f_frame['y'], **_plot_style)
        self.canvas.draw_idle()


def remove_artists(artists):
    if isinstance(artists, list):
        for artist in artists:
            remove_artists(artist)
    else:
        artists.remove()
