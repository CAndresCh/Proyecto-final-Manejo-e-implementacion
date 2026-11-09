import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os
import hashlib
import zipfile
from datetime import datetime
from fpdf import FPDF

ARCHIVO_DATOS = "contactos.dat"
ARCHIVO_INDICE = "indice.json"
ARCHIVO_HASH = "contactos.sha256"
TAMANO_REGISTRO = 100

L_ID, L_NOM, L_TEL, L_COR, L_CIU = 5, 30, 15, 30, 20

def cargar_indice():
    if not os.path.exists(ARCHIVO_INDICE):
        return {}
    try:
        with open(ARCHIVO_INDICE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def guardar_indice(indice):
    with open(ARCHIVO_INDICE, "w", encoding="utf-8") as f:
        json.dump(indice, f)

def formatear_registro(id_c, nombre, tel, correo, ciudad):
    return (str(id_c)[:L_ID].ljust(L_ID) +
            nombre[:L_NOM].ljust(L_NOM) +
            tel[:L_TEL].ljust(L_TEL) +
            correo[:L_COR].ljust(L_COR) +
            ciudad[:L_CIU].ljust(L_CIU))

def actualizar_hash():
    if not os.path.exists(ARCHIVO_DATOS):
        return
    sha256 = hashlib.sha256()
    with open(ARCHIVO_DATOS, "rb") as f:
        sha256.update(f.read())
    with open(ARCHIVO_HASH, "w", encoding="utf-8") as f:
        f.write(sha256.hexdigest())

def verificar_integridad():
    if not os.path.exists(ARCHIVO_DATOS) or not os.path.exists(ARCHIVO_HASH):
        return True
    with open(ARCHIVO_HASH, "r", encoding="utf-8") as f:
        hash_guardado = f.read().strip()
    sha256 = hashlib.sha256()
    with open(ARCHIVO_DATOS, "rb") as f:
        sha256.update(f.read())
    return hash_guardado == sha256.hexdigest()

def agregar_contacto(id_c, nombre, tel, correo, ciudad):
    indice = cargar_indice()
    if str(id_c) in indice:
        raise ValueError("El ID ya existe.")
    registro = formatear_registro(id_c, nombre, tel, correo, ciudad)
    if not os.path.exists(ARCHIVO_DATOS):
        open(ARCHIVO_DATOS, "w").close()
    with open(ARCHIVO_DATOS, "r+", encoding="utf-8") as f:
        f.seek(0, 2)
        posicion_byte = f.tell()
        num_registro = posicion_byte // TAMANO_REGISTRO
        f.write(registro)
    indice[str(id_c)] = num_registro
    guardar_indice(indice)
    actualizar_hash()

def buscar_contacto(id_c):
    indice = cargar_indice()
    if str(id_c) not in indice:
        return None
    num_registro = indice[str(id_c)]
    posicion = num_registro * TAMANO_REGISTRO
    with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
        f.seek(posicion)
        datos = f.read(TAMANO_REGISTRO)
    return {
        "id": datos[0:L_ID].strip(),
        "nombre": datos[L_ID:L_ID+L_NOM].strip(),
        "telefono": datos[L_ID+L_NOM:L_ID+L_NOM+L_TEL].strip(),
        "correo": datos[L_ID+L_NOM+L_TEL:L_ID+L_NOM+L_TEL+L_COR].strip(),
        "ciudad": datos[L_ID+L_NOM+L_TEL+L_COR:TAMANO_REGISTRO].strip()
    }

def modificar_contacto(id_c, nombre, tel, correo, ciudad):
    indice = cargar_indice()
    if str(id_c) not in indice:
        raise ValueError("El ID no existe.")
    num_registro = indice[str(id_c)]
    posicion = num_registro * TAMANO_REGISTRO
    registro = formatear_registro(id_c, nombre, tel, correo, ciudad)
    with open(ARCHIVO_DATOS, "r+", encoding="utf-8") as f:
        f.seek(posicion)
        f.write(registro)
    actualizar_hash()

class AgendaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Agenda de Contactos")
        self.root.geometry("400x300")
        if not verificar_integridad():
            messagebox.showwarning("Advertencia", "El archivo de datos fue modificado externamente.")
        self.crear_menu()
        tk.Label(root, text="Agenda de Contactos - Versión Final", font=("Arial", 14)).pack(pady=50)

    def crear_menu(self):
        menubar = tk.Menu(self.root)
        
        menu_contactos = tk.Menu(menubar, tearoff=0)
        menu_contactos.add_command(label="Agregar", command=self.ui_agregar)
        menu_contactos.add_command(label="Buscar", command=self.ui_buscar)
        menu_contactos.add_command(label="Modificar", command=self.ui_modificar)
        menubar.add_cascade(label="Contactos", menu=menu_contactos)
        
        menu_exportar = tk.Menu(menubar, tearoff=0)
        menu_exportar.add_command(label="Exportar a JSON y PDF", command=self.ui_exportar)
        menubar.add_cascade(label="Exportar", menu=menu_exportar)
        
        menu_herram = tk.Menu(menubar, tearoff=0)
        menu_herram.add_command(label="Verificar Integridad", command=self.ui_integridad)
        menu_herram.add_command(label="Crear Respaldo", command=self.ui_respaldo)
        menu_herram.add_command(label="Información del Archivo", command=self.ui_info)
        menubar.add_cascade(label="Herramientas", menu=menu_herram)
        
        self.root.config(menu=menubar)

    def solicitar_datos(self, id_default="", nom_def="", tel_def="", cor_def="", ciu_def=""):
        id_c = simpledialog.askstring("Input", "ID del contacto (Max 5 chars):", initialvalue=id_default)
        if not id_c: return None
        nom = simpledialog.askstring("Input", "Nombre:", initialvalue=nom_def)
        tel = simpledialog.askstring("Input", "Teléfono:", initialvalue=tel_def)
        cor = simpledialog.askstring("Input", "Correo:", initialvalue=cor_def)
        ciu = simpledialog.askstring("Input", "Ciudad:", initialvalue=ciu_def)
        return id_c, nom, tel, cor, ciu

    def ui_agregar(self):
        datos = self.solicitar_datos()
        if datos:
            try:
                agregar_contacto(*datos)
                messagebox.showinfo("Éxito", "Contacto agregado correctamente.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def ui_buscar(self):
        id_c = simpledialog.askstring("Buscar", "Ingrese ID a buscar:")
        if not id_c: return
        contacto = buscar_contacto(id_c)
        if contacto:
            msg = f"ID: {contacto['id']}\nNombre: {contacto['nombre']}\nTel: {contacto['telefono']}\nCorreo: {contacto['correo']}\nCiudad: {contacto['ciudad']}"
            messagebox.showinfo("Contacto Encontrado", msg)
        else:
            messagebox.showwarning("No encontrado", "El ID no existe en la agenda.")

    def ui_modificar(self):
        id_c = simpledialog.askstring("Modificar", "Ingrese ID a modificar:")
        if not id_c: return
        contacto = buscar_contacto(id_c)
        if not contacto:
            messagebox.showwarning("No encontrado", "El ID no existe en la agenda.")
            return
        datos = self.solicitar_datos(contacto['id'], contacto['nombre'], contacto['telefono'], contacto['correo'], contacto['ciudad'])
        if datos:
            try:
                modificar_contacto(*datos)
                messagebox.showinfo("Éxito", "Contacto modificado correctamente.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def ui_exportar(self):
        try:
            indice = cargar_indice()
            contactos = []
            for id_c in indice.keys():
                contactos.append(buscar_contacto(id_c))
            with open("contactos_exportados.json", "w", encoding="utf-8") as f:
                json.dump(contactos, f, indent=4)
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Reporte de Contactos - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
            for c in contactos:
                linea = f"{c['id']} | {c['nombre']} | {c['telefono']} | {c['correo']} | {c['ciudad']}"
                pdf.cell(200, 10, txt=linea, ln=True)
            pdf.output("reporte_contactos.pdf")
            messagebox.showinfo("Éxito", "Datos exportados a JSON y PDF correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al exportar: {e}")

    def ui_integridad(self):
        if verificar_integridad():
            messagebox.showinfo("Integridad", "El archivo está íntegro y sin alteraciones.")
        else:
            messagebox.showerror("Integridad", "PELIGRO: El archivo fue alterado externamente.")

    def ui_respaldo(self):
        try:
            tamano_original = 0
            archivos = [ARCHIVO_DATOS, ARCHIVO_INDICE, ARCHIVO_HASH]
            for arch in archivos:
                if os.path.exists(arch):
                    tamano_original += os.path.getsize(arch)
            with zipfile.ZipFile("respaldo.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
                for arch in archivos:
                    if os.path.exists(arch):
                        zipf.write(arch)
            tamano_comprimido = os.path.getsize("respaldo.zip")
            messagebox.showinfo("Respaldo", f"Tamaño original: {tamano_original} bytes\nTamaño comprimido: {tamano_comprimido} bytes")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def ui_info(self):
        if not os.path.exists(ARCHIVO_DATOS):
            messagebox.showwarning("Aviso", "No hay datos.")
            return
        stats = os.stat(ARCHIVO_DATOS)
        tamano = stats.st_size
        fecha_mod = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        lectura = "Sí" if os.access(ARCHIVO_DATOS, os.R_OK) else "No"
        escritura = "Sí" if os.access(ARCHIVO_DATOS, os.W_OK) else "No"
        msg = f"Tamaño: {tamano} bytes\nModificado: {fecha_mod}\nLectura: {lectura}\nEscritura: {escritura}"
        messagebox.showinfo("Metadatos", msg)

root = tk.Tk()
app = AgendaApp(root)
root.mainloop()