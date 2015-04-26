import numpy
import socket
import qt
import os
import unittest
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import BaseHTTPServer
import urllib
import SocketServer
import mimetypes
import time
from multiprocessing import Process
import multiprocessing
import threading
import httplib
import SimpleHTTPServer
import ctypes
import struct
#
# SlicerCardboard
#

class SlicerCardboard(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SlicerCardboard" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Virtual Reality"]
    self.parent.dependencies = []
    self.parent.contributors = ["Utsav Pardasani"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
    """
    self.parent.acknowledgementText = """
""" # replace with organization, grant and thanks.
    self.logic = SlicerCardboardLogic(self.parent.path)
#
# SlicerCardboardWidget
#

class SlicerCardboardWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Instantiate and connect widgets ...
    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
 
    self.layout.addStretch(1)

    # Refresh Apply button state
    
  def cleanup(self):
    pass

  def onApplyButton(self):
    logic = SlicerCardboardLogic()
    logic.run()

#
# SlicerCardboardLogic
#

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
            return
        elif self.path == '/index.html':
            content_type = 'text/html; charset=utf-8'
            with open('/home/utsav/Dropbox/SlicerExtensions/SlicerCardboard/SlicerCardboard/SlicerCardboard/index.html', 'r') as f:
                self.index_template = f.read()
            content = self.server.index_template.replace(
                    '@ADDRESS@',
                    '%s:%d' % (self.request.getsockname()[0], self.server.WSPort))
        else:
            self.send_error(404, 'File not found')
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(content))
        self.send_header('Last-Modified', self.date_time_string(time.time()))
        self.end_headers()
        if self.command == 'GET':
            self.wfile.write(content)
    def do_QUIT (self):
            """send 200 OK response, and set server.stop to True"""
            self.send_response(200)
            self.end_headers()
            self.server.stop=1
            


# From http://code.activestate.com/recipes/336012-stoppable-http-server/
class StoppableHttpServer (BaseHTTPServer.HTTPServer):
    def __init__(self, port):
       BaseHTTPServer.HTTPServer.__init__(self, ('', port), RequestHandler)
       self.WSPort = port+1
       with open('/home/utsav/Dropbox/SlicerExtensions/SlicerCardboard/SlicerCardboard/SlicerCardboard/index.html', 'r') as f:
           self.index_template = f.read()
    
    """http server that reacts to self.stop flag"""
    allow_reuse_address = 1 
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
    def serve_forever (self):
        """Handle one request at a time until stopped."""
        self.stop = False
        while not self.stop:
            self.handle_request()
        self.server_close()
        self.shutdown()
        

from ws4py.websocket import WebSocket        
class StreamingWebSocket(WebSocket):
    def received_message(self, message):
        """
        Automatically sends back the provided ``message`` to
        its originating endpoint.
        """
        self.send(message.data, message.is_binary)

     
def startwebsocket(port,q):
    from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
    from ws4py.server.wsgiutils import WebSocketWSGIApplication
    from wsgiref.simple_server import make_server
    websocket_server = make_server('', port,
                                   server_class=WSGIServer,
                                   handler_class=WebSocketWSGIRequestHandler,
                                   app=WebSocketWSGIApplication(handler_cls=StreamingWebSocket))
    websocket_server.initialize_websockets_manager()
    while 1:
        websocket_server.handle_request()
        websocket_server.timeout=0.001
        if (q.empty()==False):
            try:
                websocket_server.manager.broadcast(q.get(False), binary=True)
            except:
                pass


        
class SlicerCardboardLogic(ScriptedLoadableModuleLogic):
    httpdProcess=None
    PORT= 8080
    websocket_server=None;
    lock = multiprocessing.Lock()
    def __init__(self,path):
        self.path= path
        
    
    def OnRender(self,obj, ev):
        if (obj.GetRenderWindow().GetStereoType()!=9):
            viewNode = slicer.util.getNodes('vtkMRMLViewNode*').values()[0]
            if viewNode != None:
                viewNode.SetStereoType(6)
            obj.GetRenderWindow().SetStereoTypeToSplitViewportHorizontal()
        if self.q.empty():
            self.w2i.Update()
            self.w2i.Modified()
            self.writer.SetInputData(self.w2i.GetOutput())
            self.writer.Write()
            resultVtkCharArray = self.writer.GetResult() 
            pointer = resultVtkCharArray.GetVoidPointer(0)
            pointer = pointer[1:17]
            pointer = int(pointer,16)
            outputstring=(ctypes.string_at(pointer, resultVtkCharArray.GetMaxId()))
            try:
                self.q.put(outputstring,True,0.05)
            except:
                pass
            
            
            
    def run(self):
        httpd =  StoppableHttpServer(self.PORT)
        
        self.httpdProcess = Process(target=httpd.serve_forever)
        self.q= multiprocessing.Queue(1)
        websocket_process = Process(target=startwebsocket, args=(8081,self.q))
        import sys
               
        oldstdin = sys.stdin;
        oldstdout = sys.stdout;
        oldstderr = sys.stderr;
        filein = open("/home/utsav/tmp/stdin","r")
        fileout = open("/home/utsav/tmp/stdout","w")
        fileerr = open("/home/utsav/tmp/stderr","w")
        sys.stdin = filein;
        sys.stdout = fileout;
        sys.stderr = fileerr;
        print "starting"
        websocket_process.start()
        self.httpdProcess.start()
        
        sys.stdin = oldstdin;
        sys.stdout = oldstdout;
        sys.stderr = oldstderr;
        ren = slicer.app.layoutManager().activeThreeDRenderer()

        self.w2i = vtk.vtkWindowToImageFilter()
        self.w2i.SetInput(ren.GetRenderWindow())
        self.w2i.SetInputBufferTypeToRGBA()
        self.w2i.ShouldRerenderOff()
        
        self.writer = vtk.vtkJPEGWriter()
        self.writer.WriteToMemoryOn()
        
        viewNode = slicer.util.getNodes('vtkMRMLViewNode*').values()[0]
        viewNode.SetStereoType(6)
        ren.GetRenderWindow().SetStereoTypeToSplitViewportHorizontal()
        ren.GetRenderWindow().Render()
        ren.AddObserver('EndEvent',self.OnRender)        

    def stop(self):
        try:
            conn = httplib.HTTPConnection("localhost:%d" % self.PORT, timeout=1)
            conn.request("QUIT", "/")
            conn.getresponse()
        except:
            pass

    def test(self):
        print self.path
            

class SlicerCardboardTest(ScriptedLoadableModuleTest):
  
  def setUp(self):
      pass
#    slicer.mrmlScene.Clear(0)

  def runTest(self):
    #logic = SlicerCardboardLogic("/home/utsav/Dropbox/SlicerExtensions/SlicerCardboard/SlicerCardboard/SlicerCardboard/")
    logic = SlicerCardboardLogic("C:\\Users\\upardasani\\Dropbox\\SlicerExtensions\\SlicerCardboard\\SlicerCardboard\\SlicerCardboard\\index.html")
    logic.stop()
    logic.run()

    
    #time.sleep(30)

if __name__ == '__main__':
    test = SlicerCardboardTest()
    test.runTest()