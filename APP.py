import os
import sqlite3
from functools import wraps

from flask import Flask, request, redirect, session
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# La clave secreta se puede cambiar con una variable de entorno
app.secret_key = os.environ.get("CLAVE_SECRETA", "clave_sistema_negocio")


# ---------------------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------------------
def conectar():
    db = sqlite3.connect("negocio.db")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")  # activa las claves foráneas
    return db


with conectar() as db:
    db.execute("""CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        documento TEXT UNIQUE NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS prestamos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        monto REAL,
        total REAL,
        saldo REAL,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prestamo_id INTEGER NOT NULL,
        monto REAL,
        FOREIGN KEY(prestamo_id) REFERENCES prestamos(id)
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        correo TEXT PRIMARY KEY,
        clave TEXT NOT NULL
    )""")

    # Usuario inicial: la clave se guarda cifrada (hash), no en texto plano
    db.execute(
        "INSERT OR IGNORE INTO usuarios (correo, clave) VALUES (?, ?)",
        ("admin@negocio.com", generate_password_hash("1234"))
    )


# ---------------------------------------------------------------
# DISEÑO (se usa en todas las páginas)
# ---------------------------------------------------------------
ESTILO = """
<style>
    body {
        margin: 0;
        min-height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
        font-family: Arial, sans-serif;
        background: linear-gradient(135deg, #0f9b8e, #1565c0);
    }
    .tarjeta {
        background: white;
        width: 90%;
        max-width: 480px;
        margin: 20px 0;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        text-align: center;
    }
    h1 { color: #0b5d70; margin-top: 0; }
    h2 { color: #1565c0; }
    label { display: block; text-align: left; margin-top: 10px; color: #333; }
    input, select {
        width: 100%;
        padding: 10px;
        margin-top: 5px;
        box-sizing: border-box;
        border: 1px solid #bbb;
        border-radius: 8px;
        font-size: 16px;
    }
    button, .boton {
        display: inline-block;
        margin-top: 15px;
        padding: 10px 20px;
        background: #0f9b8e;
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 16px;
        text-decoration: none;
        cursor: pointer;
    }
    button:hover, .boton:hover { background: #0b7a70; }
    .menu .boton { display: block; margin: 12px 0; }
    .mensaje {
        background: #e0f4f1;
        color: #0b5d70;
        padding: 10px;
        border-radius: 8px;
    }
    ul { text-align: left; padding-left: 20px; }
    li { margin-bottom: 8px; }
    a { color: #1565c0; }
</style>
"""


def pagina(contenido):
    """Pone el contenido dentro de la tarjeta centrada."""
    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Sistema de pequeños negocios</title>"
        + ESTILO +
        "</head><body><div class='tarjeta'>" + contenido + "</div></body></html>"
    )


def aviso(mensaje):
    """Muestra el mensaje solo si hay uno."""
    if mensaje:
        return f"<p class='mensaje'>{escape(mensaje)}</p>"
    return ""


# ---------------------------------------------------------------
# PROTECCIÓN DE PÁGINAS
# ---------------------------------------------------------------
def requiere_login(funcion):
    @wraps(funcion)
    def revisar(*args, **kwargs):
        if not session.get("usuario"):
            return redirect("/login")
        return funcion(*args, **kwargs)
    return revisar


# ---------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    mensaje = ""

    if request.method == "POST":
        correo = request.form["correo"].strip()
        clave = request.form["clave"]

        with conectar() as db:
            usuario = db.execute(
                "SELECT * FROM usuarios WHERE correo=?", (correo,)
            ).fetchone()

        # Se compara la clave escrita con el hash guardado
        if usuario and check_password_hash(usuario["clave"], clave):
            session["usuario"] = correo
            return redirect("/")

        mensaje = "Correo o contraseña incorrectos."

    return pagina(f"""
    <h1>Iniciar sesión</h1>
    {aviso(mensaje)}
    <form method="post">
        <label>Correo</label>
        <input name="correo" type="email" required>
        <label>Clave</label>
        <input name="clave" type="password" required>
        <button>Ingresar</button>
    </form>
    """)


# ---------------------------------------------------------------
# MENÚ PRINCIPAL
# ---------------------------------------------------------------
@app.route("/")
@requiere_login
def inicio():
    return pagina("""
    <h1>Sistema de pequeños negocios</h1>
    <div class="menu">
        <a class="boton" href="/clientes">Registrar clientes</a>
        <a class="boton" href="/prestamos">Registrar préstamos</a>
        <a class="boton" href="/logout">Cerrar sesión</a>
    </div>
    """)


# ---------------------------------------------------------------
# CLIENTES
# ---------------------------------------------------------------
@app.route("/clientes", methods=["GET", "POST"])
@requiere_login
def clientes():
    mensaje = ""

    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        documento = request.form["documento"].strip()

        if not nombre or not documento:
            mensaje = "Completa todos los campos."
        else:
            try:
                with conectar() as db:
                    db.execute(
                        "INSERT INTO clientes (nombre, documento) VALUES (?, ?)",
                        (nombre, documento)
                    )
                mensaje = "Cliente registrado correctamente."
            except sqlite3.IntegrityError:
                mensaje = "Ese documento ya está registrado."

    with conectar() as db:
        lista = db.execute("SELECT * FROM clientes").fetchall()

    # escape() evita que se pueda meter código HTML en el nombre
    resultado = "".join(
        f"<li>{escape(c['nombre'])} - Documento: {escape(c['documento'])}</li>"
        for c in lista
    )

    return pagina(f"""
    <h1>Clientes</h1>
    {aviso(mensaje)}
    <form method="post">
        <label>Nombre</label>
        <input name="nombre" required>
        <label>Documento</label>
        <input name="documento" required>
        <button>Guardar cliente</button>
    </form>
    <h2>Clientes registrados</h2>
    <ul>{resultado}</ul>
    <a class="boton" href="/">Volver al menú</a>
    """)


# ---------------------------------------------------------------
# PRÉSTAMOS
# ---------------------------------------------------------------
@app.route("/prestamos", methods=["GET", "POST"])
@requiere_login
def prestamos():
    mensaje = ""

    if request.method == "POST":
        try:
            cliente_id = int(request.form["cliente_id"])
            monto = float(request.form["monto"])
            tasa = float(request.form["tasa"])
            meses = int(request.form["meses"])

            if monto <= 0 or tasa < 0 or meses <= 0:
                raise ValueError

            if monto > 1_000_000_000 or tasa > 100 or meses > 600:
                raise ValueError

            with conectar() as db:
                cliente = db.execute(
                    "SELECT id FROM clientes WHERE id=?", (cliente_id,)
                ).fetchone()

                if not cliente:
                    mensaje = "El cliente no existe."
                else:
                    interes = tasa / 100

                    if interes == 0:
                        cuota = monto / meses
                    else:
                        cuota = monto * interes / (
                            1 - (1 + interes) ** (-meses)
                        )

                    # round() evita decimales raros como 21423.120000001
                    total = round(round(cuota, 2) * meses, 2)

                    db.execute(
                        """INSERT INTO prestamos (cliente_id, monto, total, saldo)
                        VALUES (?, ?, ?, ?)""",
                        (cliente_id, monto, total, total)
                    )

                    mensaje = (
                        f"Préstamo registrado. Cuota aproximada: "
                        f"${cuota:,.2f}. Total: ${total:,.2f}"
                    )

        except (ValueError, TypeError):
            mensaje = "Revisa los datos ingresados."

    with conectar() as db:
        clientes_lista = db.execute("SELECT * FROM clientes").fetchall()

        prestamos_lista = db.execute("""
            SELECT prestamos.*, clientes.nombre
            FROM prestamos
            JOIN clientes ON clientes.id = prestamos.cliente_id
        """).fetchall()

    opciones = "".join(
        f"<option value='{c['id']}'>{escape(c['nombre'])}</option>"
        for c in clientes_lista
    )

    filas = ""
    for p in prestamos_lista:
        if p["saldo"] > 0:
            accion = f"<a href='/pago/{p['id']}'>Registrar pago</a>"
        else:
            accion = "<b>Pagado ✔</b>"

        filas += (
            f"<li>{escape(p['nombre'])} - Monto: ${p['monto']:,.2f} "
            f"- Saldo: ${p['saldo']:,.2f} - {accion}</li>"
        )

    if clientes_lista:
        formulario = f"""
        <form method="post">
            <label>Cliente</label>
            <select name="cliente_id" required>{opciones}</select>
            <label>Monto</label>
            <input name="monto" type="number" min="1" step="0.01" required>
            <label>Interés mensual (%)</label>
            <input name="tasa" type="number" min="0" step="0.01" value="2" required>
            <label>Plazo en meses</label>
            <input name="meses" type="number" min="1" required>
            <button>Calcular y guardar</button>
        </form>
        """
    else:
        formulario = "<p>Primero debes <a href='/clientes'>registrar un cliente</a>.</p>"

    return pagina(f"""
    <h1>Préstamos</h1>
    {aviso(mensaje)}
    {formulario}
    <h2>Préstamos registrados</h2>
    <ul>{filas}</ul>
    <a class="boton" href="/">Volver al menú</a>
    """)


# ---------------------------------------------------------------
# PAGOS
# ---------------------------------------------------------------
@app.route("/pago/<int:id>", methods=["GET", "POST"])
@requiere_login
def pago(id):
    mensaje = ""

    with conectar() as db:
        prestamo = db.execute(
            "SELECT * FROM prestamos WHERE id=?", (id,)
        ).fetchone()

    if prestamo is None:
        return pagina("<p>Préstamo no encontrado.</p>"
                      "<a class='boton' href='/prestamos'>Volver</a>")

    if request.method == "POST":
        try:
            monto = round(float(request.form["monto"]), 2)

            if monto <= 0 or monto > prestamo["saldo"] + 0.005:
                mensaje = "El pago no es válido o supera el saldo."
            else:
                saldo = max(round(prestamo["saldo"] - monto, 2), 0)

                with conectar() as db:
                    db.execute(
                        "INSERT INTO pagos (prestamo_id, monto) VALUES (?, ?)",
                        (id, monto)
                    )
                    db.execute(
                        "UPDATE prestamos SET saldo=? WHERE id=?",
                        (saldo, id)
                    )

                mensaje = f"Pago guardado. Saldo pendiente: ${saldo:,.2f}"

        except ValueError:
            mensaje = "Escribe un valor numérico válido."

    with conectar() as db:
        pagos = db.execute(
            "SELECT * FROM pagos WHERE prestamo_id=?", (id,)
        ).fetchall()

        prestamo = db.execute(
            "SELECT * FROM prestamos WHERE id=?", (id,)
        ).fetchone()

    historial = "".join(
        f"<li>Pago de ${p['monto']:,.2f}</li>" for p in pagos
    )

    return pagina(f"""
    <h1>Registrar pago</h1>
    <p><b>Saldo actual: ${prestamo['saldo']:,.2f}</b></p>
    {aviso(mensaje)}
    <form method="post">
        <label>Valor del pago</label>
        <input name="monto" type="number" min="0.01" step="0.01" required>
        <button>Guardar pago</button>
    </form>
    <h2>Historial de pagos</h2>
    <ul>{historial}</ul>
    <a class="boton" href="/prestamos">Volver a préstamos</a>
    """)


# ---------------------------------------------------------------
# CERRAR SESIÓN
# ---------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run()