import functools
import hashlib
import json
import os
import re
import tkinter as tk
import zipfile
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from fpdf import FPDF
except ImportError:  # el resto de la app funciona sin fpdf
    FPDF = None
    
# ───────────────────────── Configuración ─────────────────────────
ARCHIVO_DATOS = "contactos.dat"
ARCHIVO_INDICE = "indice.json"
ARCHIVO_HASH = "contactos.sha256"
TAMANO_REGISTRO = 100

# (clave, etiqueta, longitud en bytes)  -> suman 100 bytes, igual que antes
CAMPOS = [
    ("id", "ID", 5),
    ("nombre", "Nombre", 30),
    ("telefono", "Teléfono", 15),
    ("correo", "Correo", 30),
    ("ciudad", "Ciudad", 20),
]
LONGITUD = {k: n for k, _, n in CAMPOS}

RE_TEL = re.compile(r"^[\d\s+\-()]{7,15}$")
RE_MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RE_ID = re.compile(r"[0-9]+")


# ───────────────────────── Capa de datos ─────────────────────────
def _ajustar(texto, n):
    """Recorta a n BYTES (utf-8) sin cortar caracteres y rellena con espacios."""
    b = (texto or "").encode("utf-8")[:n]
    b = b.decode("utf-8", "ignore").encode("utf-8")
    return b.ljust(n)


def formatear_registro(datos):
    return b"".join(_ajustar(datos[k], n) for k, _, n in CAMPOS)


def parsear_registro(raw):
    datos, pos = {}, 0
    for k, _, n in CAMPOS:
        datos[k] = raw[pos:pos + n].decode("utf-8", "replace").strip()
        pos += n
    return datos


def _hash_archivo():
    sha = hashlib.sha256()
    with open(ARCHIVO_DATOS, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            sha.update(bloque)
    return sha.hexdigest()


def actualizar_hash():
    if os.path.exists(ARCHIVO_DATOS):
        with open(ARCHIVO_HASH, "w", encoding="utf-8") as f:
            f.write(_hash_archivo())


def verificar_integridad():
    if not os.path.exists(ARCHIVO_DATOS) or not os.path.exists(ARCHIVO_HASH):
        return True
    with open(ARCHIVO_HASH, "r", encoding="utf-8") as f:
        return f.read().strip() == _hash_archivo()


def leer_todos():
    """Lee el archivo secuencialmente. Devuelve (contactos, registros_borrados)."""
    contactos, borrados = [], 0
    if not os.path.exists(ARCHIVO_DATOS):
        return contactos, borrados
    with open(ARCHIVO_DATOS, "rb") as f:
        while True:
            raw = f.read(TAMANO_REGISTRO)
            if len(raw) < TAMANO_REGISTRO:
                break
            c = parsear_registro(raw)
            if c["id"]:
                contactos.append(c)
            else:
                borrados += 1
    return contactos, borrados


def reconstruir_indice():
    indice = {}
    if os.path.exists(ARCHIVO_DATOS):
        with open(ARCHIVO_DATOS, "rb") as f:
            num = 0
            while True:
                raw = f.read(TAMANO_REGISTRO)
                if len(raw) < TAMANO_REGISTRO:
                    break
                ident = parsear_registro(raw)["id"]
                if ident:
                    indice[ident] = num
                num += 1
    guardar_indice(indice)
    return indice


def cargar_indice():
    if not os.path.exists(ARCHIVO_INDICE):
        return reconstruir_indice()
    try:
        with open(ARCHIVO_INDICE, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            raise ValueError("índice con formato inválido")
        return datos
    except (OSError, ValueError):  # JSONDecodeError es subclase de ValueError
        return reconstruir_indice()


def guardar_indice(indice):
    tmp = ARCHIVO_INDICE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(indice, f)
    os.replace(tmp, ARCHIVO_INDICE)  # escritura atómica


def validar(datos, nuevo=True):
    """Devuelve un dict {campo: mensaje_de_error}."""
    errores = {}
    if not datos["id"]:
        errores["id"] = "El ID es obligatorio."
    elif not RE_ID.fullmatch(datos["id"]):
        errores["id"] = "El ID debe ser un número entero."
    if not datos["nombre"]:
        errores["nombre"] = "El nombre es obligatorio."
    if datos["telefono"] and not RE_TEL.match(datos["telefono"]):
        errores["telefono"] = "Teléfono inválido (7-15 dígitos, + - ( ))."
    if datos["correo"] and not RE_MAIL.match(datos["correo"]):
        errores["correo"] = "Correo electrónico inválido."
    for k, etiqueta, n in CAMPOS:
        if k not in errores and len(datos[k].encode("utf-8")) > n:
            errores[k] = f"{etiqueta}: máximo {n} caracteres."
    return errores


def agregar_contacto(datos):
    """Añade al final del archivo. Devuelve la traza de seek()/tell()."""
    indice = cargar_indice()
    if datos["id"] in indice:
        raise ValueError("El ID ya existe.")
    if not os.path.exists(ARCHIVO_DATOS):
        open(ARCHIVO_DATOS, "wb").close()
    with open(ARCHIVO_DATOS, "r+b") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()                      # tell(): posición donde se escribirá
        num = pos // TAMANO_REGISTRO
        f.write(formatear_registro(datos))
        fin = f.tell()                      # tell(): posición tras escribir
    indice[datos["id"]] = num
    guardar_indice(indice)
    actualizar_hash()
    return {"registro": num, "seek": pos, "tell": fin}


def buscar_contacto(id_c, traza=None):
    """Busca por ID: índice -> seek() directo al registro (sin leer todo el archivo)."""
    indice = cargar_indice()
    for _ in range(2):
        if id_c not in indice:
            return None
        num = indice[id_c]
        pos = num * TAMANO_REGISTRO
        with open(ARCHIVO_DATOS, "rb") as f:
            f.seek(pos)                     # salto directo
            raw = f.read(TAMANO_REGISTRO)
            fin = f.tell()                  # tell(): posición tras leer
        if len(raw) == TAMANO_REGISTRO:
            c = parsear_registro(raw)
            if c["id"] == id_c:
                if traza is not None:
                    traza.update(registro=num, seek=pos, tell=fin)
                return c
        indice = reconstruir_indice()       # índice desactualizado: se reconstruye
    return None


def modificar_contacto(datos):
    """Sobrescribe solo el registro indicado (modificación en el lugar)."""
    indice = cargar_indice()
    if datos["id"] not in indice:
        raise ValueError("El ID no existe.")
    num = indice[datos["id"]]
    with open(ARCHIVO_DATOS, "r+b") as f:
        f.seek(num * TAMANO_REGISTRO)
        pos = f.tell()
        f.write(formatear_registro(datos))
        fin = f.tell()
    actualizar_hash()
    return {"registro": num, "seek": pos, "tell": fin}


def eliminar_contacto(id_c):
    indice = cargar_indice()
    if id_c not in indice:
        raise ValueError("El ID no existe.")
    with open(ARCHIVO_DATOS, "r+b") as f:
        f.seek(indice[id_c] * TAMANO_REGISTRO)
        f.write(b" " * TAMANO_REGISTRO)  # hueco reutilizable/ignorado
    del indice[id_c]
    guardar_indice(indice)
    actualizar_hash()


# ───────────────────────── Interfaz ─────────────────────────
C = {
    "primario": "#2563eb", "primario_h": "#1d4ed8",
    "peligro": "#dc2626", "peligro_h": "#b91c1c",
    "fondo": "#f1f5f9", "tarjeta": "#ffffff", "header": "#0f172a",
    "texto": "#0f172a", "suave": "#64748b", "borde": "#e2e8f0",
    "fila_alt": "#f8fafc", "sel": "#dbeafe",
}
FUENTE = ("Segoe UI", 10)


def aplicar_estilos(root):
    st = ttk.Style(root)
    st.theme_use("clam")
    root.configure(bg=C["fondo"])
    st.configure(".", font=FUENTE, background=C["fondo"], foreground=C["texto"])
    st.configure("Card.TFrame", background=C["tarjeta"])
    st.configure("TLabel", background=C["fondo"])
    st.configure("Card.TLabel", background=C["tarjeta"])
    st.configure("Err.TLabel", background=C["tarjeta"], foreground=C["peligro"], font=("Segoe UI", 8))

    st.configure("TButton", padding=(14, 7), borderwidth=0, background="#e2e8f0")
    st.map("TButton", background=[("active", "#cbd5e1")])
    st.configure("Accent.TButton", background=C["primario"], foreground="white", font=("Segoe UI", 10, "bold"))
    st.map("Accent.TButton", background=[("active", C["primario_h"])])
    st.configure("Danger.TButton", background=C["peligro"], foreground="white")
    st.map("Danger.TButton", background=[("active", C["peligro_h"])])

    st.configure("TEntry", padding=6, fieldbackground="white", bordercolor=C["borde"], lightcolor=C["borde"], darkcolor=C["borde"])
    st.map("TEntry", bordercolor=[("focus", C["primario"])], lightcolor=[("focus", C["primario"])])

    st.configure("Treeview", rowheight=30, background="white", fieldbackground="white",
                 foreground=C["texto"], borderwidth=0, font=FUENTE)
    st.map("Treeview", background=[("selected", C["sel"])], foreground=[("selected", C["texto"])])
    st.configure("Treeview.Heading", background="#e2e8f0", foreground=C["texto"],
                 font=("Segoe UI", 10, "bold"), padding=(8, 8), borderwidth=0)
    st.map("Treeview.Heading", background=[("active", "#cbd5e1")])


def seguro(fn):
    """Evita que la app se caiga por errores de archivos (permisos, inexistentes, corruptos)."""
    @functools.wraps(fn)
    def envoltura(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except PermissionError:
            messagebox.showerror("Sin permisos", "No hay permisos para acceder a un archivo de la agenda.")
        except FileNotFoundError as e:
            messagebox.showerror("Archivo no encontrado", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))
    return envoltura


class FormularioContacto(tk.Toplevel):
    """Diálogo modal para crear/editar un contacto con validación en línea."""

    def __init__(self, parent, titulo, contacto=None):
        super().__init__(parent)
        self.title(titulo)
        self.configure(bg=C["tarjeta"])
        self.resizable(False, False)
        self.transient(parent)
        self.resultado = None
        self.editando = contacto is not None
        contacto = contacto or {}

        marco = ttk.Frame(self, style="Card.TFrame", padding=24)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=titulo, style="Card.TLabel",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self.vars, self.err = {}, {}
        self.entradas = {}
        for i, (k, etiqueta, n) in enumerate(CAMPOS):
            fila = 1 + i * 2
            ttk.Label(marco, text=etiqueta, style="Card.TLabel",
                      foreground=C["suave"]).grid(row=fila, column=0, sticky="w", padx=(0, 14))
            var = tk.StringVar(value=contacto.get(k, ""))
            ent = ttk.Entry(marco, textvariable=var, width=32)
            ent.grid(row=fila, column=1, sticky="ew", pady=(4, 0))
            if k == "id" and self.editando:
                ent.state(["disabled"])
            lbl = ttk.Label(marco, text="", style="Err.TLabel")
            lbl.grid(row=fila + 1, column=1, sticky="w")
            self.vars[k], self.err[k], self.entradas[k] = var, lbl, ent

        botones = ttk.Frame(marco, style="Card.TFrame")
        botones.grid(row=20, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(botones, text="Guardar", style="Accent.TButton", command=self.guardar).pack(side="right")

        self.bind("<Return>", lambda e: self.guardar())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.entradas["nombre" if self.editando else "id"].focus_set()
        self.grab_set()
        self.wait_window()

    def guardar(self):
        datos = {k: v.get().strip() for k, v in self.vars.items()}
        if RE_ID.fullmatch(datos["id"]):
            datos["id"] = str(int(datos["id"]))  # "007" -> "7"
        errores = validar(datos, nuevo=not self.editando)
        for k, lbl in self.err.items():
            lbl.config(text=errores.get(k, ""))
        if errores:
            self.entradas[next(iter(errores))].focus_set()
            return
        self.resultado = datos
        self.destroy()


class AgendaApp:
    def __init__(self, root):
        self.root = root
        root.title("Agenda de Contactos")
        root.geometry("900x580")
        root.minsize(720, 420)
        aplicar_estilos(root)

        self.contactos = []
        self.orden = ("id", False)
        self.busqueda = tk.StringVar()
        self.busqueda.trace_add("write", lambda *_: self.refrescar())

        self.crear_menu()
        self.crear_header()
        self.crear_toolbar()
        self.crear_tabla()
        self.crear_statusbar()
        self.crear_atajos()

        self.cargar()
        try:
            integro = verificar_integridad()
        except OSError as e:
            integro = True
            messagebox.showwarning("Integridad", f"No se pudo verificar la integridad:\n{e}")
        if not integro:
            if messagebox.askyesno(
                    "Advertencia de integridad",
                    "El archivo de datos fue modificado externamente.\n\n"
                    "¿Desea aceptar el estado actual como válido?"):
                actualizar_hash()

    # ---------- construcción ----------
    def crear_menu(self):
        mb = tk.Menu(self.root)
        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Nuevo contacto\tCtrl+N", command=self.nuevo)
        m.add_command(label="Buscar por ID\tCtrl+B", command=self.buscar)
        m.add_command(label="Editar\tEnter", command=self.editar)
        m.add_command(label="Eliminar\tSupr", command=self.eliminar)
        m.add_separator()
        m.add_command(label="Salir", command=self.root.destroy)
        mb.add_cascade(label="Contactos", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Exportar a JSON y PDF…", command=self.exportar)
        mb.add_cascade(label="Exportar", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Verificar integridad", command=self.integridad)
        m.add_command(label="Crear respaldo…", command=self.respaldo)
        m.add_command(label="Información del archivo", command=self.info)
        mb.add_cascade(label="Herramientas", menu=m)

        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Manual de usuario (simulado)", command=self.manual)
        m.add_command(label="Acerca de…", command=self.acerca)
        mb.add_cascade(label="Ayuda", menu=m)
        self.root.config(menu=mb)

    def crear_header(self):
        h = tk.Frame(self.root, bg=C["header"])
        h.pack(fill="x")
        tk.Label(h, text="📒  Agenda de Contactos", bg=C["header"], fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20, pady=14)
        self.lbl_total = tk.Label(h, text="", bg=C["header"], fg="#94a3b8", font=FUENTE)
        self.lbl_total.pack(side="right", padx=20)

    def crear_toolbar(self):
        t = ttk.Frame(self.root, padding=(16, 14, 16, 6))
        t.pack(fill="x")
        ttk.Button(t, text="＋  Nuevo", style="Accent.TButton", command=self.nuevo).pack(side="left")
        ttk.Button(t, text="🔎  Buscar ID", command=self.buscar).pack(side="left", padx=8)
        ttk.Button(t, text="✎  Editar", command=self.editar).pack(side="left", padx=(0, 8))
        ttk.Button(t, text="🗑  Eliminar", style="Danger.TButton", command=self.eliminar).pack(side="left")
        self.entry_busq = ttk.Entry(t, textvariable=self.busqueda, width=30)
        self.entry_busq.pack(side="right")
        ttk.Label(t, text="🔍 Buscar:").pack(side="right", padx=(0, 8))

    def crear_tabla(self):
        card = ttk.Frame(self.root, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=16, pady=(6, 8))
        cols = [k for k, _, _ in CAMPOS]
        self.tree = ttk.Treeview(card, columns=cols, show="headings", selectmode="browse")
        anchos = {"id": 70, "nombre": 220, "telefono": 130, "correo": 230, "ciudad": 130}
        for k, etiqueta, _ in CAMPOS:
            self.tree.heading(k, text=etiqueta, command=lambda c=k: self.ordenar(c))
            self.tree.column(k, width=anchos[k], minwidth=60, anchor="w")
        self.tree.tag_configure("alt", background=C["fila_alt"])
        sb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self.editar())
        self.tree.bind("<Return>", lambda e: self.editar())
        self.tree.bind("<Delete>", lambda e: self.eliminar())
        self.tree.bind("<Button-3>", self.menu_contextual)
        self.tree.bind("<Button-2>", self.menu_contextual)  # macOS

        self.ctx = tk.Menu(self.root, tearoff=0)
        self.ctx.add_command(label="Editar", command=self.editar)
        self.ctx.add_command(label="Copiar correo", command=lambda: self.copiar("correo"))
        self.ctx.add_command(label="Copiar teléfono", command=lambda: self.copiar("telefono"))
        self.ctx.add_separator()
        self.ctx.add_command(label="Eliminar", command=self.eliminar)

        self.lbl_vacio = ttk.Label(card, text="No hay contactos para mostrar.\nPulsa «Nuevo» para agregar el primero.",
                                   style="Card.TLabel", foreground=C["suave"], justify="center")

    def crear_statusbar(self):
        self.estado = tk.StringVar(value="Listo")
        tk.Label(self.root, textvariable=self.estado, anchor="w", bg=C["borde"],
                 fg=C["suave"], font=("Segoe UI", 9), padx=12, pady=4).pack(fill="x", side="bottom")

    def crear_atajos(self):
        self.root.bind("<Control-n>", lambda e: self.nuevo())
        self.root.bind("<Control-b>", lambda e: self.buscar())
        self.root.bind("<Control-f>", lambda e: (self.entry_busq.focus_set(), self.entry_busq.select_range(0, "end")))
        self.root.bind("<F5>", lambda e: self.cargar())

    # ---------- datos en pantalla ----------
    def cargar(self):
        try:
            self.contactos, _ = leer_todos()
        except PermissionError:
            self.contactos = []
            messagebox.showerror("Sin permisos", f"No hay permisos de lectura sobre {ARCHIVO_DATOS}.")
        except OSError as e:
            self.contactos = []
            messagebox.showerror("Error de archivo", str(e))
        self.refrescar()

    def refrescar(self):
        sel = self.tree.selection()
        q = self.busqueda.get().strip().lower()
        filas = [c for c in self.contactos if not q or any(q in c[k].lower() for k in c)]
        col, desc = self.orden
        if col == "id" and all(c["id"].isdigit() for c in filas):
            filas.sort(key=lambda c: int(c["id"]), reverse=desc)
        else:
            filas.sort(key=lambda c: c[col].lower(), reverse=desc)

        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(filas):
            self.tree.insert("", "end", iid=c["id"], values=[c[k] for k, _, _ in CAMPOS],
                             tags=("alt",) if i % 2 else ())
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])

        if filas:
            self.lbl_vacio.place_forget()
        else:
            self.lbl_vacio.place(relx=0.5, rely=0.5, anchor="center")
        self.lbl_total.config(text=f"{len(self.contactos)} contacto(s)")
        self.estado.set(f"Mostrando {len(filas)} de {len(self.contactos)}")

        for k, etiqueta, _ in CAMPOS:  # flecha de orden
            flecha = (" ▼" if desc else " ▲") if k == col else ""
            self.tree.heading(k, text=etiqueta + flecha)

    def ordenar(self, col):
        self.orden = (col, not self.orden[1] if self.orden[0] == col else False)
        self.refrescar()

    def seleccionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Selecciona un contacto", "Primero selecciona un contacto de la lista.")
            return None
        return sel[0]

    def menu_contextual(self, e):
        fila = self.tree.identify_row(e.y)
        if fila:
            self.tree.selection_set(fila)
            self.ctx.tk_popup(e.x_root, e.y_root)

    def copiar(self, campo):
        sel = self.tree.selection()
        if sel:
            c = next(x for x in self.contactos if x["id"] == sel[0])
            self.root.clipboard_clear()
            self.root.clipboard_append(c[campo])
            self.estado.set(f"{campo.capitalize()} copiado al portapapeles")

    # ---------- acciones ----------
    def nuevo(self):
        datos = FormularioContacto(self.root, "Nuevo contacto").resultado
        if not datos:
            return
        try:
            traza = agregar_contacto(datos)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.cargar()
        self.tree.selection_set(datos["id"])
        self.tree.see(datos["id"])
        self.estado.set(f"Agregado «{datos['nombre']}» → registro {traza['registro']} | "
                        f"seek({traza['seek']}) | tell() tras escribir = {traza['tell']}")

    def buscar(self):
        """Búsqueda por ID usando el índice y seek() (requisito del laboratorio)."""
        id_c = simpledialog.askstring("Buscar por ID", "Ingrese el ID del contacto:", parent=self.root)
        if id_c is None:
            return
        id_c = id_c.strip()
        if not RE_ID.fullmatch(id_c):
            messagebox.showwarning("ID inválido", "El ID debe ser un número entero.")
            return
        id_c = str(int(id_c))
        traza = {}
        try:
            c = buscar_contacto(id_c, traza)
        except PermissionError:
            messagebox.showerror("Sin permisos", "No hay permisos para leer el archivo de contactos.")
            return
        except OSError as e:
            messagebox.showerror("Error de archivo", str(e))
            return
        if c is None:
            messagebox.showwarning("No encontrado", f"El ID {id_c} no existe en la agenda.")
            return
        messagebox.showinfo(
            "Contacto encontrado",
            f"ID: {c['id']}\nNombre: {c['nombre']}\nTeléfono: {c['telefono']}\n"
            f"Correo: {c['correo']}\nCiudad: {c['ciudad']}\n\n"
            f"── Acceso aleatorio ──\n"
            f"Índice: ID {id_c} → registro N.º {traza['registro']}\n"
            f"seek({traza['registro']} × {TAMANO_REGISTRO}) = byte {traza['seek']}\n"
            f"tell() tras leer = byte {traza['tell']}")
        if self.tree.exists(id_c):
            self.tree.selection_set(id_c)
            self.tree.see(id_c)

    def manual(self):
        messagebox.showinfo("Manual de usuario (simulado)",
                            "Esta sección es simulada según el enunciado del laboratorio.\n\n"
                            "• Contactos: agregar, buscar por ID, modificar y eliminar.\n"
                            "• Exportar: genera JSON y PDF.\n"
                            "• Herramientas: integridad, respaldo ZIP e información del archivo.")

    def acerca(self):
        messagebox.showinfo("Acerca de", "Agenda de Contactos con Acceso Aleatorio\n"
                                         "Laboratorio No. 2 – Manejo de archivos\n"
                                         "Registros de 100 bytes · índice JSON · SHA-256")

    def editar(self):
        id_c = self.seleccionado()
        if not id_c:
            return
        try:
            actual = buscar_contacto(id_c)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if actual is None:
            messagebox.showwarning("No encontrado", "El ID no existe en la agenda.")
            return
        datos = FormularioContacto(self.root, "Editar contacto", actual).resultado
        if not datos:
            return
        try:
            traza = modificar_contacto(datos)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.cargar()
        self.estado.set(f"Actualizado «{datos['nombre']}» → registro {traza['registro']} | "
                        f"seek({traza['seek']}) | tell() tras escribir = {traza['tell']}")

    def eliminar(self):
        id_c = self.seleccionado()
        if not id_c:
            return
        c = next(x for x in self.contactos if x["id"] == id_c)
        if messagebox.askyesno("Eliminar contacto", f"¿Eliminar a «{c['nombre']}»?\nEsta acción no se puede deshacer."):
            try:
                eliminar_contacto(id_c)
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return
            self.cargar()
            self.estado.set("Contacto eliminado")

    def exportar(self):
        if not self.contactos:
            messagebox.showinfo("Exportar", "No hay contactos para exportar.")
            return
        carpeta = filedialog.askdirectory(title="Carpeta de destino")
        if not carpeta:
            return
        try:
            ruta_json = os.path.join(carpeta, "contactos_exportados.json")
            contactos, _ = leer_todos()
            with open(ruta_json, "w", encoding="utf-8") as f:
                json.dump(contactos, f, indent=4, ensure_ascii=False)
            msg = f"JSON guardado en:\n{ruta_json}"
            if FPDF is None:
                msg += "\n\nPara generar el PDF instala fpdf2:\npip install fpdf2"
            else:
                ruta_pdf = os.path.join(carpeta, "reporte_contactos.pdf")
                with open(ruta_json, "r", encoding="utf-8") as f:  # el PDF se genera a partir del JSON
                    desde_json = json.load(f)
                self._pdf(ruta_pdf, desde_json)
                msg += f"\n\nPDF guardado en:\n{ruta_pdf}"
            messagebox.showinfo("Exportación completada", msg)
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al exportar: {e}")

    def _pdf(self, ruta, contactos):
        def t(s):  # fuentes base del PDF solo admiten latin-1
            return s.encode("latin-1", "replace").decode("latin-1")

        anchos = [15, 50, 32, 58, 35]
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, t("Reporte de Contactos"), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 6, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)
        pdf.set_fill_color(37, 99, 235)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        for (_, etiqueta, _), w in zip(CAMPOS, anchos):
            pdf.cell(w, 8, t(etiqueta), border=0, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=9)
        for i, c in enumerate(sorted(contactos, key=lambda c: c["nombre"].lower())):
            pdf.set_fill_color(241, 245, 249) if i % 2 else pdf.set_fill_color(255, 255, 255)
            for (k, _, _), w in zip(CAMPOS, anchos):
                pdf.cell(w, 7, t(c[k]), fill=True)
            pdf.ln()
        pdf.output(ruta)

    @seguro
    def integridad(self):
        if verificar_integridad():
            messagebox.showinfo("Integridad", "✔ El archivo está íntegro y sin alteraciones.")
        elif messagebox.askyesno("Integridad", "⚠ El archivo fue alterado externamente.\n\n"
                                               "¿Aceptar el estado actual como válido?"):
            actualizar_hash()
            self.cargar()

    def respaldo(self):
        nombre = f"respaldo_{datetime.now():%Y%m%d_%H%M%S}.zip"
        ruta = filedialog.asksaveasfilename(title="Guardar respaldo", defaultextension=".zip",
                                            initialfile=nombre, filetypes=[("ZIP", "*.zip")])
        if not ruta:
            return
        try:
            archivos = [a for a in (ARCHIVO_DATOS, ARCHIVO_INDICE, ARCHIVO_HASH) if os.path.exists(a)]
            original = sum(os.path.getsize(a) for a in archivos)
            with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
                for a in archivos:
                    z.write(a)
            comp = os.path.getsize(ruta)
            ahorro = 100 - comp * 100 / original if original else 0
            messagebox.showinfo("Respaldo creado",
                                f"Tamaño original: {original} bytes\nTamaño comprimido: {comp} bytes\n"
                                f"Ahorro: {ahorro:.1f}%\n\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    @seguro
    def info(self):
        if not os.path.exists(ARCHIVO_DATOS):
            messagebox.showwarning("Aviso", "Aún no hay datos.")
            return
        s = os.stat(ARCHIVO_DATOS)
        _, borrados = leer_todos()
        si = lambda ok: "Sí" if ok else "No"
        messagebox.showinfo("Información del archivo",
                            f"Archivo: {os.path.abspath(ARCHIVO_DATOS)}\n"
                            f"Tamaño: {s.st_size} bytes\n"
                            f"Contactos activos: {len(self.contactos)}\n"
                            f"Registros libres: {borrados}\n"
                            f"Modificado: {datetime.fromtimestamp(s.st_mtime):%Y-%m-%d %H:%M:%S}\n"
                            f"Lectura: {si(os.access(ARCHIVO_DATOS, os.R_OK))}\n"
                            f"Escritura: {si(os.access(ARCHIVO_DATOS, os.W_OK))}\n"
                            f"Integridad: {'correcta' if verificar_integridad() else 'ALTERADO'}")


def main():
    root = tk.Tk()
    AgendaApp(root)
    root.mainloop()


main()