import streamlit as st
import requests
import json
import os
from datetime import datetime
import urllib.parse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# Configurar vista ancha obligatoria para las 3 columnas
st.set_page_config(page_title="PokéPrice Monitor", layout="wide")

# -----------------------------------------------------------------------------
# BASE DE DATOS LOCAL (JSON)
# -----------------------------------------------------------------------------
DB_FILE = "favoritos.json"

def cargar_favoritos():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_favoritos(datos):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def agregar_a_favoritos(card_id, card_name, price_to_save, img_url, set_info):
    favoritos = cargar_favoritos()
    fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    nuevo_registro = {
        "fecha": fecha_actual,
        "precio": price_to_save
    }
    
    if card_id in favoritos:
        favoritos[card_id]["nombre"] = card_name
        favoritos[card_id]["imagen"] = img_url
        favoritos[card_id]["precio_ultimo"] = price_to_save
        favoritos[card_id]["fecha_ultima"] = fecha_actual
        favoritos[card_id]["set_info"] = set_info
        if not favoritos[card_id].get("historial") or favoritos[card_id]["historial"][-1]["fecha"] != fecha_actual:
            favoritos[card_id]["historial"].append(nuevo_registro)
    else:
        favoritos[card_id] = {
            "nombre": card_name,
            "imagen": img_url,
            "set_info": set_info,
            "precio_inicial": price_to_save,
            "fecha_inicial": fecha_actual,
            "precio_ultimo": price_to_save,
            "fecha_ultima": fecha_actual,
            "historial": [nuevo_registro]
        }
    
    guardar_favoritos(favoritos)

def eliminar_de_favoritos(card_id):
    favoritos = cargar_favoritos()
    if card_id in favoritos:
        del favoritos[card_id]
        guardar_favoritos(favoritos)

# -----------------------------------------------------------------------------
# DATOS CON ID EXACTO (ILUSTRACIONES PRECISAS Y COMPATIBLES)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def obtener_mas_vendidas_cardmarket():
    return [
        {"nombre": "Charmander (Art Rare)", "set": "151", "precio": "30.00 €", "card_id": "sv3pt5-168"},
        {"nombre": "Charizard ex (Special Art)", "set": "151", "precio": "120.00 €", "card_id": "sv3pt5-199"},
        {"nombre": "Pikachu ex", "set": "Surging Sparks", "precio": "25.00 €", "card_id": "sv08-057"},
        {"nombre": "Mewtwo ex", "set": "151", "precio": "8.00 €", "card_id": "sv3pt5-183"},
        {"nombre": "Umbreon VMAX (Alt Art)", "set": "Evolving Skies", "precio": "650.00 €", "card_id": "swsh7-215"},
        {"nombre": "Gengar ex", "set": "Temporal Forces", "precio": "15.00 €", "card_id": "sv05-104"},
        {"nombre": "Gardevoir ex", "set": "Paldean Fates", "precio": "18.00 €", "card_id": "sv04.5-233"},
        {"nombre": "Iono (Special Art)", "set": "Paldea Evolved", "precio": "35.00 €", "card_id": "sv02-269"},
        {"nombre": "Squirtle (Art Rare)", "set": "151", "precio": "25.00 €", "card_id": "sv3pt5-170"},
        {"nombre": "Bulbasaur (Art Rare)", "set": "151", "precio": "22.00 €", "card_id": "sv3pt5-166"}
    ]

@st.cache_data(ttl=3600)
def obtener_gangas_cardmarket():
    return [
        {"nombre": "Zapdos ex (Special Art)", "set": "151", "precio": "11.20 €", "card_id": "sv3pt5-202"},
        {"nombre": "Alakazam ex (Special Art)", "set": "151", "precio": "9.50 €", "card_id": "sv3pt5-201"},
        {"nombre": "Erika's Invitation", "set": "151", "precio": "14.00 €", "card_id": "sv3pt5-196"},
        {"nombre": "Arceus VSTAR", "set": "Crown Zenith", "precio": "58.00 €", "card_id": "swsh12pt5-GG70"},
        {"nombre": "Giratina V (Alt Art)", "set": "Lost Origin", "precio": "210.00 €", "card_id": "swsh11-186"},
        {"nombre": "Snorlax (Illustration)", "set": "151", "precio": "15.00 €", "card_id": "sv3pt5-181"},
        {"nombre": "Blastoise ex (Special Art)", "set": "151", "precio": "45.00 €", "card_id": "sv3pt5-200"},
        {"nombre": "Venusaur ex (Special Art)", "set": "151", "precio": "40.00 €", "card_id": "sv3pt5-198"}
    ]

# -----------------------------------------------------------------------------
# DICCIONARIO / MAPEO MULTILINGÜE Y UTILIDADES
# -----------------------------------------------------------------------------
POKEMON_TRANSLATIONS = {
    "cubone": {"zh-cn": "卡拉卡拉", "zh-tw": "卡拉卡拉", "ja": "カラカラ", "ko": "탕구리"},
    "gloom": {"zh-cn": "臭臭花", "zh-tw": "臭臭花", "ja": "クサイハナ", "ko": "냄새꼬"},
    "pikachu": {"zh-cn": "皮卡丘", "zh-tw": "皮卡丘", "ja": "ピカチュウ", "ko": "피卡츄"},
    "charizard": {"zh-cn": "喷火龙", "zh-tw": "噴火龍", "ja": "リザードン", "ko": "리자몽"}
}

def obtener_nombre_traduccion(nombre_input, lang_code):
    nombre_clean = nombre_input.strip().lower()
    if nombre_clean in POKEMON_TRANSLATIONS:
        return POKEMON_TRANSLATIONS[nombre_clean].get(lang_code, nombre_input)
    return nombre_input

RAREZA_ORDEN = {
    "corona": 100, "crown": 100, "hyper rare": 100, "rara hiper": 100, "secret rare": 100, "rara secreta": 100,
    "tres estrellas": 90, "three stars": 90, "special illustration rare": 90, "illustration rare": 80,
    "ultra rare": 70, "rara doble": 60, "rare holo": 50, "rare": 40, "uncommon": 30, "common": 20
}

def obtener_peso_rareza(card_detail):
    rarity_str = str(card_detail.get('rarity', '')).strip().lower()
    for key, weight in RAREZA_ORDEN.items():
        if key in rarity_str:
            return weight
    return 0

def obtener_detalle_carta(card_id, lang_code):
    """Consulta la carta y si falla o no existe en el idioma elegido, usa inglés de respaldo (Fallback)."""
    try:
        res = requests.get(f"https://api.tcgdex.net/v2/{lang_code}/cards/{card_id}", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    
    # Intento de respaldo en inglés si falla en español/asíatico
    try:
        res_en = requests.get(f"https://api.tcgdex.net/v2/en/cards/{card_id}", timeout=3)
        if res_en.status_code == 200:
            return res_en.json()
    except Exception:
        pass
        
    return None

def get_spanish_nm_price(card_name, card_number):
    clean_number = card_number.split('/')[-1].split('-')[-1].lstrip('0')
    if not clean_number:
        clean_number = card_number

    search_query = f"{card_name} {clean_number}"
    encoded = urllib.parse.quote(search_query)
    url = f"https://www.cardmarket.com/es/Pokemon/Products/Search?searchString={encoded}&idCategory=51&language=4&minCondition=2"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'es-ES,es;q=0.9'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            price_element = soup.find("span", class_="color-primary")
            if price_element:
                price_str = price_element.text.strip().replace("€", "").replace(",", ".").replace(" ", "").strip()
                return float(price_str), url
    except Exception:
        pass
    
    return None, url

# -----------------------------------------------------------------------------
# INTERFAZ PRINCIPAL CON 3 COLUMNAS Y PESTAÑAS
# -----------------------------------------------------------------------------
st.title("PokéPrice Monitor 📈")

tab_buscar, tab_favs = st.tabs(["🔍 Buscador y Mercado", "⭐ Mis Favoritos"])

with tab_buscar:
    col_izq, col_centro, col_der = st.columns([1.2, 2.6, 1.2])

    # --- COLUMNA IZQUIERDA: MÁS VENDIDAS ---
    with col_izq:
        st.subheader("🔥 Más Vendidas")
        st.caption("Tendencias exactas")
        mas_vendidas = obtener_mas_vendidas_cardmarket()
        
        for idx, item in enumerate(mas_vendidas, 1):
            lbl = f"#{idx} {item['nombre']}"
            if item['set']:
                lbl += f" ({item['set']})"
            if st.button(lbl, key=f"top_v_{idx}"):
                st.session_state["direct_card_id"] = item["card_id"]
                st.rerun()
            st.caption(f"💰 **{item['precio']}**")
            st.divider()

    # --- COLUMNA DERECHA: GANGAS ---
    with col_der:
        st.subheader("🏷️ Gangas")
        st.caption("Ofertas destacadas")
        gangas = obtener_gangas_cardmarket()
        
        for idx, item in enumerate(gangas, 1):
            lbl = f"🏷️ {item['nombre']}"
            if item['set']:
                lbl += f" ({item['set']})"
            if st.button(lbl, key=f"ganga_{idx}"):
                st.session_state["direct_card_id"] = item["card_id"]
                st.rerun()
            st.caption(f"⚡ **{item['precio']}**")
            st.divider()

    # --- COLUMNA CENTRAL: DETALLE Y BUSCADOR ---
    with col_centro:
        direct_id = st.session_state.get("direct_card_id", None)
        
        region_map = {
            "🌍 Europa / Occidente (ES)": "es",
            "🇬🇧 Inglés / EE.UU. (EN)": "en",
            "🇯🇵 Japón (JA)": "ja"
        }
        region_label = st.selectbox("Mercado / Región:", list(region_map.keys()))
        lang_code = region_map[region_label]

        card_details = None

        # A) Carga directa con Fallback Anti-Bloqueos
        if direct_id:
            with st.spinner("Cargando carta seleccionada..."):
                card_details = obtener_detalle_carta(direct_id, lang_code)
                
            if not card_details:
                st.error("No se pudo cargar esta variante en particular. Intenta volver al buscador.")
            
            if st.button("🔄 Volver al buscador general"):
                st.session_state["direct_card_id"] = None
                st.rerun()

        # B) Buscador normal por nombre
        else:
            default_search = st.session_state.get("search_input", "Charmander")
            pokemon_name = st.text_input("Nombre del Pokémon:", value=default_search)
            
            if pokemon_name:
                search_term = obtener_nombre_traduccion(pokemon_name, lang_code)
                search_url = f"https://api.tcgdex.net/v2/{lang_code}/cards?name={urllib.parse.quote(search_term)}"
                res = requests.get(search_url)

                if res.status_code == 200 and len(res.json()) > 0:
                    cards_list = res.json()
                    with st.spinner("Cargando cartas..."):
                        card_ids = [c.get('id') for c in cards_list if c.get('id')]
                        with ThreadPoolExecutor(max_workers=10) as executor:
                            full_details = list(executor.map(lambda c_id: obtener_detalle_carta(c_id, lang_code), card_ids))
                        full_details = [c for c in full_details if c is not None]

                    full_details_sorted = sorted(full_details, key=obtener_peso_rareza, reverse=True)
                    options = {f"✨ [{c.get('rarity','Sin Rareza')}] - {c.get('name')} ({c.get('set',{}).get('name','')} - {c.get('id')})": c for c in full_details_sorted}
                    
                    selected_label = st.selectbox("Selecciona la carta:", list(options.keys()))
                    card_details = options[selected_label]

        # --- MOSTRAR DETALLES DE LA CARTA SELECCIONADA ---
        if card_details:
            selected_id = card_details.get('id')
            selected_name = card_details.get('name')
            st.divider()
            
            set_data = card_details.get('set', {})
            set_name = set_data.get('name', 'Desconocida')
            set_id = set_data.get('id', '').upper()
            rarity_label = card_details.get('rarity', 'Sin rareza')

            st.subheader(f"{selected_name} ({selected_id.upper()})")
            st.info(f"💎 **Rareza:** {rarity_label} | 📌 **Expansión:** {set_name} ({set_id})")

            img_url = f"{card_details.get('image', '')}/high.webp" if 'image' in card_details else ""
            if img_url:
                st.image(img_url, width=220)

            pricing = card_details.get('pricing', {})
            cm_data = pricing.get('cardmarket', {}) if pricing else card_details.get('cardmarket', {})
            
            st.subheader("🌐 Precios Promedio de Mercado")
            if cm_data:
                trend = cm_data.get('trend') or cm_data.get('trendPrice') or 0
                avg7 = cm_data.get('avg7') or 0
                avg30 = cm_data.get('avg30') or 0
                
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Tendencia", f"{trend} €")
                col_b.metric("Media 7 Días", f"{avg7} €")
                col_c.metric("Media 30 Días", f"{avg30} €")
            else:
                trend = 0

            st.divider()
            card_number = selected_id.split('-')[-1]
            scraped_price, cm_url = get_spanish_nm_price(selected_name, card_number)

            if scraped_price:
                st.success(f"**Precio Mínimo ES (NM) detectado:** {scraped_price} €")
                final_price_to_save = scraped_price
            else:
                final_price_to_save = st.number_input("Introduce precio manual (€):", min_value=0.0, value=float(trend), step=0.5)

            st.link_button("👉 Abrir en Cardmarket (Filtro ES + NM)", cm_url)

            set_info_str = f"{set_name} - Rareza: {rarity_label}"
            if st.button("⭐ Guardar en Favoritos"):
                if final_price_to_save > 0:
                    agregar_a_favoritos(selected_id, selected_name, final_price_to_save, img_url, set_info_str)
                    st.toast(f"¡Guardada con precio de {final_price_to_save}€!", icon="⭐")

with tab_favs:
    st.header("Mis Cartas Guardadas")
    favoritos = cargar_favoritos()

    if not favoritos:
        st.info("Aún no has guardado ninguna carta en favoritos.")
    else:
        favoritos_ordenados = sorted(
            favoritos.items(),
            key=lambda item: item[1].get('precio_ultimo', 0),
            reverse=True
        )

        st.caption("🟢 Cartas ordenadas de **más cara a más barata**.")

        for card_id, data in favoritos_ordenados:
            with st.expander(f"💰 {data['precio_ultimo']} € — ⭐ {data['nombre']} ({card_id.upper()})"):
                col_img, col_det, col_hist = st.columns([1, 2, 2])
                
                with col_img:
                    if data.get("imagen"):
                        st.image(data["imagen"], width=130)

                with col_det:
                    if data.get("set_info"):
                        st.caption(f"📦 **Info:** {data['set_info']}")
                        
                    st.write(f"**Precio inicial:** {data['precio_inicial']} €")
                    st.write(f"**Último precio:** {data['precio_ultimo']} €")

                    dif = round(data['precio_ultimo'] - data['precio_inicial'], 2)
                    if dif > 0:
                        st.write(f"📈 **Diferencia:** +{dif} €")
                    elif dif < 0:
                        st.write(f"📉 **Diferencia:** {dif} €")
                    else:
                        st.write("⚖️ **Diferencia:** Sin cambios")

                    if st.button("❌ Eliminar", key=f"del_{card_id}"):
                        eliminar_de_favoritos(card_id)
                        st.rerun()

                with col_hist:
                    st.write("**Historial de registros:**")
                    for reg in reversed(data.get("historial", [])):
                        st.write(f"• `{reg['fecha']}`: **{reg['precio']} €**")
