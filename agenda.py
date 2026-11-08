import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os

# Constantes del archivo y registro
ARCHIVO_DATOS = "contactos.dat"
ARCHIVO_INDICE = "indice.json"
TAMANO_REGISTRO = 100

# Longitud exacta de cada campo (Total = 100)
L_ID = 5
L_NOM = 30
L_TEL = 15
L_COR = 30
L_CIU = 20

def cargar_indice():
    """Carga el índice JSON en memoria. Si no existe, devuelve un diccionario vacío."""
    if not os.path.exists(ARCHIVO_INDICE):
        return {}
    try:
        with open(ARCHIVO_INDICE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def guardar_indice(indice):
    """Sobrescribe el archivo JSON con el diccionario de índices actualizado."""
    with open(ARCHIVO_INDICE, "w", encoding="utf-8") as f:
        json.dump(indice, f)

def formatear_registro(id_c, nombre, tel, correo, ciudad):
    """Rellena cada campo con espacios a la derecha usando ljust() para asegurar el tamaño fijo."""
    return (str(id_c)[:L_ID].ljust(L_ID) +
            nombre[:L_NOM].ljust(L_NOM) +
            tel[:L_TEL].ljust(L_TEL) +
            correo[:L_COR].ljust(L_COR) +
            ciudad[:L_CIU].ljust(L_CIU))

def agregar_contacto(id_c, nombre, tel, correo, ciudad):
    """Agrega un contacto al final del archivo de datos y actualiza el índice."""
    indice = cargar_indice()
    if str(id_c) in indice:
        raise ValueError("El ID ya existe en la agenda.")
    
    registro = formatear_registro(id_c, nombre, tel, correo, ciudad)
    
    # Si el archivo no existe, lo creamos
    if not os.path.exists(ARCHIVO_DATOS):
        open(ARCHIVO_DATOS, "w").close()
        
    with open(ARCHIVO_DATOS, "r+", encoding="utf-8") as f:
        f.seek(0, 2) # Ubicar el cursor al final del archivo (0 bytes desde el final - 2)
        posicion_byte = f.tell() # Obtener la posición actual del cursor
        num_registro = posicion_byte // TAMANO_REGISTRO
        f.write(registro)
        print(f"DEBUG - Contacto guardado en el registro #{num_registro} (byte {posicion_byte})")
        
    # Actualizar y guardar el índice
    indice[str(id_c)] = num_registro
    guardar_indice(indice)

class AgendaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Agenda de Contactos")
        self.root.geometry("400x300")
        
        self.crear_menu()
        tk.Label(root, text="Agenda de Contactos - Fase 1", font=("Arial", 14)).pack(pady=50)

    def crear_menu(self):
        menubar = tk.Menu(self.root)
        
        # Menú Contactos
        menu_contactos = tk.Menu(menubar, tearoff=0)
        menu_contactos.add_command(label="Agregar", command=self.ui_agregar)
        # Las opciones de Buscar y Modificar están deshabilitadas por ahora
        menu_contactos.add_command(label="Buscar", state="disabled") 
        menu_contactos.add_command(label="Modificar", state="disabled")
        menubar.add_cascade(label="Contactos", menu=menu_contactos)
        
        self.root.config(menu=menubar)

    def ui_agregar(self):
        # Solicitamos los datos usando cuadros de diálogo sencillos
        id_c = simpledialog.askstring("Input", "ID del contacto (Max 5 chars):")
        if not id_c: return
        nombre = simpledialog.askstring("Input", "Nombre:")
        tel = simpledialog.askstring("Input", "Teléfono:")
        correo = simpledialog.askstring("Input", "Correo:")
        ciudad = simpledialog.askstring("Input", "Ciudad:")
        
        try:
            agregar_contacto(id_c, nombre, tel, correo, ciudad)
            messagebox.showinfo("Éxito", "Contacto agregado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

root = tk.Tk()
app = AgendaApp(root)
root.mainloop()