import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import pytz
from email.mime.text import MIMEText
import base64
from PIL import Image
import smtplib
import json, os

# ---------------- CONFIGURACIÓN GENERAL ----------------
st.set_page_config(page_title="💈 Lucky Bvrber 🍀", page_icon="💇", layout="wide")

# Cargar estilo CSS
try:
    with open("style/main.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("⚠️ No se encontró style/main.css")

# ---------------- IMÁGENES ----------------
def load_image(path, size=(400, 300)):
    if os.path.exists(path):
        img = Image.open(path)
        img.thumbnail(size)
        return img
    else:
        st.warning(f"No se encontró la imagen {path}")
        return None

banner = load_image("images/banner.jpg", size=(1200, 400))
if banner:
    st.image(banner, use_container_width=True)

# ---------------- DATOS DE SERVICIOS ----------------
SERVICIOS = {
    "Servicio Clasico": {"desc": "Corte de pelo a gusto, perfilado de cejas y barba, productos para estilizar el cabello." , "precio": "10.000", "imagen": "images/Corte_Clasico.jpg"},
    "Servicio Premium": {"desc": "Incluye limpieza, exfoliación e hidratación + los mismos beneficios que clásico.", "precio": "17.000", "imagen": "images/Corte_Premium.jpg"},
    "Servicio Domicilio": {"desc": "Corte de pelo a gusto en la comodidad de su casa (valor puede variar según distancia)." , "precio": "15.000", "imagen": "images/Corte_Domicilio.jpg"},
    "Servicio Tintura": {"desc": "Servicio clasico + Tintura deseada, coordinar por DM color y estilo deseado" , "precio": "45.000", "imagen": "images/tintura.jpg"},
    "Servicio Ondulacion": {"desc": "Servicio clasico + Ondulacion permanente, coordinar por DM estilo deseado" , "precio": "40.000", "imagen": "images/Ondulado_Permanente.jpg"},
}

# ---------------- CONFIGURACIÓN DE HORARIOS ----------------
WORK_START, WORK_END, SLOT_MINUTES = 9, 18, 45
TIMEZONE = "America/Santiago"
CALENDAR_ID = "lucky.bvrber5@gmail.com"
SHEET_ID = "1z4E18eS62VUacbIHb2whKzLYTsS5zyYnRNZTqFFiQgc"
tz = pytz.timezone(TIMEZONE)

# ---------------- AUTENTICACIÓN GOOGLE ----------------
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send"
]

# Cargar credenciales desde variable de entorno (Render)
creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

creds = service_account.Credentials.from_service_account_info(creds_info,scopes=SCOPES)

calendar_service = build("calendar", "v3", credentials=creds)
sheets_service = build("sheets", "v4", credentials=creds)
gmail_service = build("gmail", "v1", credentials=creds)

# ---------------- FUNCIONES ----------------
def get_day_events(service, fecha):
    start = tz.localize(datetime(fecha.year, fecha.month, fecha.day, 0, 0))
    end = start + timedelta(days=1)
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    return events.get("items", [])


def is_slot_free(start, end, events):
    for event in events:
        s = event["start"].get("dateTime")
        e = event["end"].get("dateTime")
        if s and e:
            s, e = datetime.fromisoformat(s), datetime.fromisoformat(e)
            if start < e and end > s:
                return False
    return True


def create_calendar_event(service, start, end, title, desc, email):
    event = {
        "summary": title,
        "description": desc,
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
    }
    created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created["id"]


def append_to_sheet(service, data):
    service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range="A1",
        valueInputOption="RAW",
        body={"values": [data]}
    ).execute()


def send_gmail_message(to, subject, body):
    gmail_user = "lucky.bvrber5@gmail.com"
    app_password = "bioz ttiy vput vbkl"

    msg = MIMEText(body)
    msg["From"] = gmail_user
    msg["To"] = to
    msg["Subject"] = subject

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, app_password)
            server.sendmail(gmail_user, to, msg.as_string())
        st.success("✅ Correo enviado correctamente.")
    except Exception as e:
        st.error(f"Error al enviar correo: {e}")


# ---------------- MENÚ LATERAL ----------------
menu = st.sidebar.radio("Menú", ["Reservar", "Cancelar cita"])


# =======================================================
# ===================== RESERVAR =========================
# =======================================================
if menu == "Reservar":

    st.title("💈 Reserva tu cita con 𝓛𝓾𝓬𝓴𝔂 𝐵𝓋𝓇𝒷𝑒𝓇 🍀")

    nombre = st.text_input("👤 Nombre completo")
    email = st.text_input("📧 Correo electrónico")
    fecha = st.date_input("📅 Fecha de la cita")

    if fecha:
        events = get_day_events(calendar_service, fecha)
        slots = []
        hora = WORK_START
        while hora + (SLOT_MINUTES / 60) <= WORK_END:
            start = tz.localize(datetime(fecha.year, fecha.month, fecha.day, int(hora)))
            end = start + timedelta(minutes=SLOT_MINUTES)
            if is_slot_free(start, end, events):
                slots.append(f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}")
            hora += SLOT_MINUTES / 60
        hora_sel = st.selectbox("🕒 Horas disponibles", slots) if slots else st.warning("Sin horarios libres.")
    else:
        hora_sel = None

    st.subheader("💇‍♂️ Servicios disponibles")
    cols = st.columns(len(SERVICIOS))
    for i, (nombre_servicio, datos) in enumerate(SERVICIOS.items()):
        with cols[i]:
            img = load_image(datos["imagen"])
            if img:
                st.image(img)
            st.markdown(f"**{nombre_servicio}** — {datos['desc']} — 💵 ${datos['precio']}")


    servicio = st.selectbox("✂️ Elige tu servicio", list(SERVICIOS.keys()))

    if "reserva_confirmada" not in st.session_state:
        st.session_state["reserva_confirmada"] = False

    if st.button("📆 Confirmar reserva") and not st.session_state["reserva_confirmada"]:
        if not nombre or not email or not fecha or not hora_sel:
            st.error("Por favor, completa todos los campos.")
        else:
            start_str, end_str = hora_sel.split(" - ")
            start_dt = tz.localize(datetime.combine(fecha, datetime.strptime(start_str, "%H:%M").time()))
            end_dt = tz.localize(datetime.combine(fecha, datetime.strptime(end_str, "%H:%M").time()))
            precio = SERVICIOS[servicio]["precio"]

            if not is_slot_free(start_dt, end_dt, events):
                st.error("⛔ Ese horario ya está ocupado.")
            else:
                try:
                    title = f"{servicio} — {nombre}"
                    desc = f"Cliente: {nombre}\nEmail: {email}\nServicio: {servicio}\nPrecio: ${precio}"

                    event_id = create_calendar_event(calendar_service, start_dt, end_dt, title, desc, email)

                    append_to_sheet(sheets_service, [
                        fecha.strftime("%Y-%m-%d"),
                        start_str,
                        nombre,
                        email,
                        servicio,
                        precio,
                        event_id,
                        "ACTIVA",   # ← NUEVO ESTADO
                        "",         # fecha_cancelación
                        ""          # motivo
                    ])

                    send_gmail_message(
                         email,
                        "Confirmación de cita — Lucky Barber",
                        f"Hola {nombre}, tu cita para {servicio} fue confirmada para el {fecha} a las {start_str}. 💈\nPrecio: ${precio}\n¡Te esperamos!"
                    )
                    st.success("✅ Cita confirmada y correo enviado.")
                    st.session_state["reserva_confirmada"] = True

                except HttpError as e:
                    st.error(f"Error en Google API: {e}")


# =======================================================
# ================= CANCELAR CITA ========================
# =======================================================
if menu == "Cancelar cita":

    st.title("❌ Cancelar cita")

    # Entrada para buscar por correo
    email_cancel = st.text_input("📧 Ingresa el correo con el que reservaste")

    # Buscar citas
    if st.button("Buscar mis citas"):
        sheet = sheets_service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range="A:J"
        ).execute()

        rows = sheet.get("values", [])[1:]  # sin encabezado

        citas = [r for r in rows if len(r) > 6 and r[3] == email_cancel]

        # Guardamos la info en session_state para NO perderla al recargar
        st.session_state["citas_encontradas"] = citas
        st.session_state["sheet_rows"] = rows

    # Si ya existen citas cargadas, mostrarlas
    if "citas_encontradas" in st.session_state:

        citas = st.session_state["citas_encontradas"]
        rows = st.session_state["sheet_rows"]

        if not citas:
            st.error("No se encontraron citas asociadas a ese correo.")
            st.stop()

        st.success("Citas encontradas:")

        # Crear almacenamiento para motivos
        if "motivos" not in st.session_state:
            st.session_state["motivos"] = {}

        for idx, c in enumerate(citas):
            fecha, hora, nombre, correo, servicio, precio, event_id = c[:7]
            key_cita = f"{event_id}_{idx}"

            with st.container():
                st.write(f"📅 **{fecha}** — 🕒 **{hora}** — ✂️ {servicio} — 💵 ${precio}")

                # input del motivo (persistente)
                st.session_state["motivos"][key_cita] = st.text_input(
                    f"Motivo de cancelación ({fecha} {hora}):",
                    value=st.session_state["motivos"].get(key_cita, ""),
                    key=f"motivo_input_{key_cita}"
                )

                # botón cancelar
                if st.button(f"Cancelar cita del {fecha} {hora}", key=f"btn_cancelar_{key_cita}"):

                    motivo = st.session_state["motivos"].get(key_cita, "")

                    if not motivo.strip():
                        st.error("⚠️ Debes ingresar un motivo para cancelar.")
                        st.stop()

                    try:
                        # 1. Borrar del calendar
                        calendar_service.events().delete(
                        calendarId=CALENDAR_ID,
                        eventId=event_id
                        ).execute()

                    except HttpError as e:
                        status = getattr(e.resp, "status", None)

                        if status == 410 or "Resource has been deleted" in str(e):
                            # Evento ya eliminado → continuar
                            pass
                        else:
                            st.error(f"Error al cancelar: {e}")
                            st.stop()

                    # 2. Buscar fila en Google Sheets
                    fila_real = rows.index(c) + 2

                    # 3. Actualizar estado y motivo
                    sheets_service.spreadsheets().values().update(
                        spreadsheetId=SHEET_ID,
                        range=f"H{fila_real}:J{fila_real}",
                        valueInputOption="RAW",
                        body={
                            "values": [[
                                "CANCELADA",
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                motivo
                            ]]
                        }
                    ).execute()

                    st.success("❌ Cita cancelada correctamente.")

                    # Limpiar estado para evitar doble cancelación
                    del st.session_state["citas_encontradas"]