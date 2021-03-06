import threading
import time
from datetime import datetime
import cv2
import numpy as np

from sensors.cameraFilter import CameraFilter
from parallelIce.navDataClient import NavDataClient
from parallelIce.cmdvel import CMDVel
from parallelIce.extra import Extra
from parallelIce.pose3dClient import Pose3DClient


time_cycle = 80
croppingExt = False
lin = np.zeros((360,640), np.uint8)
stop_button = False
stop = np.zeros((20, 20, 3), np.uint8)
stop[0:20, 0:20] = (0,0,255)

class MyAlgorithm(threading.Thread):
    global lin


    def __init__(self, camera, navdata, pose, cmdvel, extra):
        self.camera = camera
        self.navdata = navdata
        self.pose = pose
        self.cmdvel = cmdvel
        self.extra = extra

        self.stop_event = threading.Event()
        self.kill_event = threading.Event()
        self.lock = threading.Lock()
        threading.Thread.__init__(self, args=self.stop_event)


    def run (self):

        self.stop_event.clear()

        while (not self.kill_event.is_set()):
           
            start_time = datetime.now()

            if not self.stop_event.is_set():
                self.execute()

            finish_Time = datetime.now()

            dt = finish_Time - start_time
            ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
            #print (ms)
            if (ms < time_cycle):
                time.sleep((time_cycle - ms) / 1000.0)

    def stop (self):
        self.stop_event.set()

    def play (self):
        if self.is_alive():
            self.stop_event.clear()
        else:
            self.start()

    def kill (self):
        self.kill_event.set()

    def click_and_crop(self, event, x, y, flags, param):
        # referencias del grab a las variables globales
        global refPt, croppingExt, refMov, lin
        # Si el boton izquierdo del raton se pulsa, graba los primeros (x,y) e indica que el corte (cropping) se esta
        # realizando
        if event == cv2.EVENT_LBUTTONDOWN:
            refPt = [(x, y)]
            refMov = [(x, y)]
            croppingExt = True

        # Mira a ver si el boton izquierdo ha dejado de presionarse
        elif event == cv2.EVENT_LBUTTONUP:
            # guarda las coordenadas finales (x ,y) e indica que el corte (cropping) se ha acabado
            refPt.append((x, y))
            croppingExt = False

            # Dentro de este elif dibujo un rectangulo alrededor de la region de interes
            lin = np.zeros((360, 640), dtype=np.uint8)
            cv2.rectangle(lin, refPt[0], refPt[1], 255, 2)


        if (event == cv2.EVENT_MOUSEMOVE) and (croppingExt == True):
            if len(refMov) == 1:
                refMov.append((x, y))
                lin = np.zeros((360, 640), dtype=np.uint8)
                cv2.rectangle(lin, refMov[0], refMov[1], 255, 2)


            elif len(refMov) == 2:
                refMov[1] = ((x, y))
                lin = np.zeros((360, 640), dtype=np.uint8)
                cv2.rectangle(lin, refMov[0], refMov[1], 255, 2)

    def stop_screen(self, event, x, y, flags, param ):
        global stop_button, lin
        if (event == cv2.EVENT_LBUTTONDBLCLK) and (stop_button == False):
            stop_button = True


    def execute(self):
        # Add your code here
        global lin, stop, stop_button, stop, refPt, refMov


        # Captamos la imagen de la camara y la pasamos a escala de grises.
        frame1 = self.camera.getImage()
        gray_frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        # La imagen que tenemos al mostrar ROI SELECTION es de tamaño {360, 640], por eso tenemos que 
        # quedarnos con parte de la imagen captada por la camara
        gray_frame1 = gray_frame1[60:420, 0:640]
        # Suma de la imagen en escala de grises con la imagen de ceros
        img = cv2.add(gray_frame1, lin)
        cv2.imshow('ROI SELECTION', img)
        # Llamamos a la funcion click_and_crop cuando se captura un evento de raton
        cv2.setMouseCallback('ROI SELECTION', self.click_and_crop)


        while (True):
            frame = self.camera.getImage()
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_frame = gray_frame[60:420, 0:640]
            img_tru = cv2.add(gray_frame, lin)
            cv2.imshow('ROI SELECTION', img_tru)
            # Miramos si se pulsa Enter en el teclado
            key = cv2.waitKey(1) & 0xFF
            if key == 13:
                # Si ya hemos marcado la zona de interes, entonces destruimos la ventana con la imagen ROI SELECTION, de no ser asi continuamos con el codigo
                # Ponemos el boton de stop a false, ya que no lo hemos pulsado
                if len(refPt) == 2:
                    cv2.destroyWindow('ROI SELECTION')
                    stop_button = False
                    break
                else:
                    continue

        # Cogemos la ultima imagen capturada con la camara y cogemos solamente una imagen de tamaño (360, 640)
        frame_final = self.camera.getImage()
        frame_final_cut = frame_final[60:420, 0:640]
        # la funcion cv2.medianBlur() toma la mediana de todos los pixeles bajo el area del kernel y el elemento central 
        # se sustituye por este valor mediana. Esto es muy eficaz contra el ruido de sal y pimienta en las imagenes. 
        frame_final_cut = cv2.medianBlur(frame_final_cut, 3)
        frame_final_cut_gray = cv2.cvtColor(frame_final_cut, cv2.COLOR_BGR2GRAY)
        # La funcion cv2.goodFeaturesToTrack encuentra bordes en la imagen de entrada y los marca en los bordes del mapa de salida usando el algoritmo de Canny. 
        p0 = cv2.goodFeaturesToTrack(frame_final_cut_gray, 100, 0.01, 10, None, None, 7)
        index = 0
        for i in (p0):
            # Si la posicion de algun punto del borde esta fuera del rectangulo de interes, entonces borramos una fila (axis=0) desde la posicion index
            if (i[0][0] < refPt[0][0]) or (i[0][0] > refPt[1][0]) or (i[0][1] < refPt[0][1]) or (i[0][1] > refPt[1][1]):
                p0 = np.delete(p0, index, axis=0)
            else:
                # Si no hemos tenido que borrar, entonces sumamos 1 a index
                index = index + 1
        

        while (stop_button == False):

            # Si el boton de stop no ha sido pulsado, capturamos una imagen de la camara, nos quedamos con parte de la imagen (360, 640),
            # eliminamos ruido sal y pimienta, y pasamos la imagen a escala de grises
            frame_final2 = self.camera.getImage()
            frame_final_cut2 = frame_final2[60:420, 0:640]
            frame_final_cut2 = cv2.medianBlur(frame_final_cut2, 3)
            frame_final_cut2_gray = cv2.cvtColor(frame_final_cut2, cv2.COLOR_BGR2GRAY)
            # La funcion cv2.calcOpticalFlowPyrLK calcula un flujo óptico para un conjunto de características escasas utilizando el metodo iterativo Lucas-Kanade con piramides.
            p1, st, err = cv2.calcOpticalFlowPyrLK(frame_final_cut_gray, frame_final_cut2_gray, p0, None,
                                                   None, None,
                                                   (30, 30), 2,
                                                   (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

            # Seleccionamos el punto bueno
            good_p1 = p1[st==1]
            # Devuelve el maximo valor del eje 0
            maxAll = np.amax(good_p1, axis = 0)
            # Devuelve el mininimo valor del eje 0
            minAll = np.amin(good_p1, axis = 0)
            # Cogemos cada una de las coordenadas de los arrays anteriores
            maxX = maxAll[0]#[0]
            maxY = maxAll[1]#[1]
            minX = minAll[0]#[0]
            minY = minAll[1]#[1]
            """
            if (maxX-minX) < 50:
                maxX = maxX + 50
                minX = minX - 50
            if (maxY-minY) < 50:
                maxY = maxY + 50
                minY = minY-50
            """
            # Dibujamos los vectores de movimiento, y un circulo en el comienzo del vector y otro circulo al final
            for i,(f2,f1) in enumerate(zip(p1,p0)):
                a, b = f2.ravel()
                c, d = f1.ravel()
                cv2.circle(frame_final_cut2, (a, b), 5, (255, 255, 0), -1)
                cv2.circle(frame_final_cut2, (c, d), 5, (255, 0, 0), -1)
                cv2.line(frame_final_cut2, (a, b), (c, d), (0,0,255), 2)

            # En la ultima imagen capturada por la camara dibuja un rectangulo desde el minimo hasta el maximo de donde se produce movimiento
            cv2.rectangle(frame_final_cut2, (np.int0(minX), np.int0(minY)), (np.int0(maxX), np.int0(maxY)), (0,255,0), 2)

            # Mostramos una ventana con un boton para parar de calcular el flujo optico. Si, pulsamos en la ventana, se vuelve a cargar la ventana de ROI SELECTION
            cv2.imshow("DOUBLE-CLICK STOP BUTTON", stop)
            cv2.setMouseCallback("DOUBLE-CLICK STOP BUTTON", self.stop_screen)
            if frame_final_cut2 is not None:
                self.camera.setColorImage(frame_final_cut2)

            frame_final_cut_gray = np.copy(frame_final_cut2_gray)


            # La funcion cv2.goodFeaturesToTrack encuentra bordes en la imagen de entrada y los marca en los bordes del mapa de salida usando el algoritmo de Canny. 
            p0 = cv2.goodFeaturesToTrack(frame_final_cut_gray, 100, 0.01, 10, None, None, 7)
            index2 = 0
            for p in (p0):
                if (p[0][0] < (np.int0(minX) -2) or p[0][0] > (np.int0(maxX) +2)) or (p[0][1] < (np.int0(minY)-2) or p[0][1] > (np.int0(maxY)+2)):
                    p0 = np.delete(p0, index2, axis=0)
                else:
                    index2 = index2 + 1

            if len(p0)<10:
                cv2.rectangle(frame_final_cut2, (np.int0(minX), np.int0(minY)), (np.copy(maxX), np.int0(maxY)), (0, 255, 0), 2)
                p0 = cv2.goodFeaturesToTrack(frame_final_cut_gray, 100, 0.01, 10, None, None, 7)
                index3 = 0
                for g in (p0):
                    if ((g[0][0] < (minX - 20)) or (g[0][0] > (maxX + 20))) or ((g[0][1] < (minY - 20)) or (g[0][1] > (maxY + 20))):
                        p0 = np.delete(p0, index3, axis=0)
                    else:
                        index3 = index3 + 1

        # Destruimos la ventana del boton de stop, y ponenemos las variables con el valor de inicio
        cv2.destroyWindow("DOUBLE-CLICK STOP BUTTON")
        refPt = []
        refMov = []
        lin = np.zeros((360, 640), dtype=np.uint8)



#http://synnick.blogspot.com.es/2013/05/reporte-de-proyecto-deteccion-de.html


