import streamlit as st
import requests
import json
import os
from datetime import datetime
import urllib.parse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# Configurar vista ancha para que quepa bien el sidebar y el contenido
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
        if not favoritos[card_id]["historial"] or favoritos[card_id]["historial"][-1]["fecha"] != fecha_actual:
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
# SCRAPING / OBTENCIÓN DEL TOP 20 MÁS VENDIDAS / TENDENCIAS
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def obtener_top_20_tendencias_exactas():
    """Extrae las 20 cartas con mayor tendencia en Cardmarket."""
    url = "https://www.cardmarket.com/es/Pokemon/Products/Singles"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9'
    }
    
    top_cards = []
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            rows = soup.select('.table-body .row')
            for row in rows[:20]:
                name_elem = row.select_one('.col-seller, .col-name, a')
                set_elem = row.select_one('.col-expansion, .expansion-symbol')
                price_elem = row.select_one('.col-price')
                
                if name_elem:
                    card_title = name_elem.text.strip()
                    set_title = set_elem.text.strip() if set_elem else ""
                    price_val = price_elem.text.strip() if price_elem else "N/D"
                    
                    top_cards.append({
                        "nombre": card_title,
                        "set": set_title,
                        "precio": price_val
                    })
    except Exception:
        pass

    # Si falla por Cloudflare, cargamos una lista de respaldo ampliada a 20 cartas
    if not top_cards:
        top_cards = [
            {"nombre": "Charizard ex", "set": "Obsidian Flames", "precio": "12.50 €"},
            {"nombre": "Pikachu ex", "set": "Surging Sparks", "precio": "25.00 €"},
            {"nombre": "Mewtwo ex", "set": "151", "precio": "8.00 €"},
            {"nombre": "Umbreon VMAX", "set": "Evolving Skies", "precio": "650.00 €"},
            {"nombre": "Gengar ex", "set": "Temporal Forces", "precio": "15.00 €"},
            {"nombre": "Gardevoir ex", "set": "Paldean Fates", "precio": "18.00 €"},
            {"nombre": "Iono", "set": "Paldea Evolved", "precio": "35.00 €"},
            {"nombre": "Lugia V", "set": "Silver Tempest", "precio": "180.00 €"},
            {"nombre": "Giratina V", "set": "Lost Origin", "precio": "240.00 €"},
            {"nombre": "Rayquaza VMAX", "set": "Evolving Skies", "precio": "300.00 €"},
            {"nombre": "Bulbasaur", "set": "151", "precio": "22.00 €"},
            {"nombre": "Squirtle", "set": "151", "precio": "25.00 €"},
            {"nombre": "Charmander", "set": "151", "precio": "30.00 €"},
            {"nombre": "Blastoise ex", "set": "151", "precio": "45.00 €"},
            {"nombre": "Venusaur ex", "set": "151", "precio": "40.00 €"},
            {"nombre": "Eevee", "set": "Twilight Masquerade", "precio": "48.00 €"},
            {"nombre": "Snorlax", "set": "151", "precio": "15.00 €"},
            {"nombre": "Arceus VSTAR", "set": "Crown Zenith", "precio": "65.00 €"},
            {"nombre": "Miriam", "set": "Scarlet & Violet", "precio": "32.00 €"},
            {"nombre": "Lillie", "set": "Ultra Prism", "precio": "120.00 €"}
        ]
    return top_cards

# -----------------------------------------------------------------------------
# DICCIONARIO / MAPEO MULTILINGÜE
# -----------------------------------------------------------------------------
POKEMON_TRANSLATIONS = {
    "cubone": {"zh-cn": "卡拉卡拉", "zh-tw": "卡拉卡拉", "ja": "カラカラ", "ko": "탕구리"},
    "gloom": {"zh-cn": "臭臭花", "zh-tw": "臭臭花", "ja": "クサイハナ", "ko": "냄새꼬"},
    "pikachu": {"zh-cn": "皮卡丘", "zh-tw": "皮卡丘", "ja": "ピカチュウ", "ko": "皮卡丘"},
    "charizard": {"zh-cn": "喷火龙", "zh-tw": "噴火龍", "ja": "リザードン", "ko": "리자몽"}
}

def obtener_nombre_traduccion(nombre_input, lang_code):
    nombre_clean = nombre_input.strip().lower()
    if nombre_clean in POKEMON_TRANSLATIONS:
        return POKEMON_TRANSLATIONS[nombre_clean].get(lang_code, nombre_input)
    return nombre_input

# -----------------------------------------------------------------------------
# RAREZA & APIS
# -----------------------------------------------------------------------------
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
    try:
        res = requests.get(f"https://api.tcgdex.net/v2/{lang_code}/cards/{card_id}", timeout=5)
        if res.status_code == 200:
            return res.json()
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
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
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# BARRA LATERAL (SIDEBAR): TOP 20 TENDENCIAS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🔥 Top 20 Tendencias")
    st.caption("Impresiones más populares")
    
    top_20 = obtener_top_20_tendencias_exactas()
    
    for idx, item in enumerate(top_20, 1):
        label = f"#{idx} {item['nombre']}"
        if item['set']:
            label += f" ({item['set']})"
            
        with st.container():
            if st.button(label, key=f"top_exact_{idx}"):
                # Enviamos solo el nombre del Pokémon/carta para que la API no falle
                st.session_state["search_input"] = item["nombre"]
                st.rerun()
            st.caption(f"💰 Precio tendencia: **{item['precio']}**")
            st.divider()
# -----------------------------------------------------------------------------
# INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------
st.title("PokéPrice Monitor 📈")

tab_buscar, tab_favs = st.tabs(["🔍 Buscar Cartas", "⭐ Mis Favoritos"])

with tab_buscar:
    col_search, col_lang = st.columns([3, 2])
    
    # Manejar estado del buscador desde la barra lateral
    default_search = st.session_state.get("search_input", "Gloom")

    with col_search:
        pokemon_name = st.text_input("Nombre del Pokémon:", value=default_search)
    
    with col_lang:
        region_map = {
            "🌍 Europa / Occidente (ES)": "es",
            "🇬🇧 Inglés / EE.UU. (EN)": "en",
            "🇯🇵 Japón (JA)": "ja",
            "🇨🇳 China Simplificada (ZH-CN)": "zh-cn",
            "🇹🇼 China Tradicional / Taiwán (ZH-TW)": "zh-tw",
            "🇰🇷 Corea (KO)": "ko"
        }
        
        region_label = st.selectbox("Mercado / Región:", list(region_map.keys()))
        lang_code = region_map[region_label]

    if pokemon_name:
        search_term = obtener_nombre_traduccion(pokemon_name, lang_code)
        
        if search_term != pokemon_name.strip():
            st.caption(f"ℹ️ Traducido automáticamente para {region_label}: **{search_term}**")

        search_url = f"https://api.tcgdex.net/v2/{lang_code}/cards?name={urllib.parse.quote(search_term)}"
        res = requests.get(search_url)

        if res.status_code == 200 and len(res.json()) > 0:
            cards_list = res.json()
            
            with st.spinner(f"Cargando cartas de la región [{region_label}]..."):
                card_ids = [c.get('id') for c in cards_list if c.get('id')]
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    full_details = list(executor.map(lambda c_id: obtener_detalle_carta(c_id, lang_code), card_ids))
                
                full_details = [c for c in full_details if c is not None]

            full_details_sorted = sorted(full_details, key=obtener_peso_rareza, reverse=True)

            options = {}
            for c in full_details_sorted:
                c_id = c.get('id', '')
                c_name = c.get('name', 'Sin nombre')
                c_rarity = c.get('rarity', 'Sin Rareza')
                options[f"✨ [{c_rarity}] - {c_name} ({c_id})"] = c

            selected_label = st.selectbox("Selecciona la carta (Ordenadas por RAREZA):", list(options.keys()))
            card_details = options[selected_label]
            selected_id = card_details.get('id')
            selected_name = card_details.get('name')

            st.divider()
            
            set_data = card_details.get('set', {})
            set_name = set_data.get('name', 'Desconocida')
            set_id = set_data.get('id', '').upper()
            release_date = set_data.get('releaseDate', 'Año no disponible')
            release_year = release_date.split('-')[0] if '-' in release_date else release_date
            rarity_label = card_details.get('rarity', 'Sin rareza')

            st.subheader(f"{card_details.get('name')} ({selected_id.upper()})")
            
            st.info(f"""
            💎 **Rareza:** {rarity_label}  
            📌 **Expansión:** {set_name} ({set_id})  
            📅 **Año de lanzamiento:** {release_year} | 🌐 **Región:** {region_label}
            """)

            img_url = f"{card_details.get('image', '')}/high.webp" if 'image' in card_details else ""
            if img_url:
                st.image(img_url, width=220)

            pricing = card_details.get('pricing', {})
            cm_data = pricing.get('cardmarket', {}) if pricing else card_details.get('cardmarket', {})
            
            st.subheader("🌐 Precios Promedio de Mercado (API Global)")
            if cm_data:
                trend = cm_data.get('trend') or cm_data.get('trendPrice') or cm_data.get('trend-holo') or 0
                avg7 = cm_data.get('avg7') or cm_data.get('avg7-holo') or 0
                avg30 = cm_data.get('avg30') or cm_data.get('avg30-holo') or 0
                
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Tendencia Actual", f"{trend} €")
                col_b.metric("Media 7 Días", f"{avg7} €")
                col_c.metric("Media 30 Días", f"{avg30} €")
            else:
                trend = 0
                st.info("Sin datos de API de precios para esta versión asiática.")

            st.divider()

            # SECCIÓN CARDMARKET
            st.subheader("🇪🇸 Oferta en Español / Asignación de Precio")
            card_number = selected_id.split('-')[-1]

            if lang_code in ["zh-cn", "zh-tw", "ja", "ko"]:
                st.caption("⚠️ *Atención: Cardmarket opera casi exclusivamente con el mercado Occidental.*")

            scraped_price, cm_url = get_spanish_nm_price(selected_name, card_number)

            col_es_val, col_es_btn = st.columns(2)

            with col_es_val:
                if scraped_price:
                    st.success(f"**Precio Mínimo ES (NM) detectado:** {scraped_price} €")
                    final_price_to_save = scraped_price
                else:
                    default_val = float(trend) if trend else 0.0
                    final_price_to_save = st.number_input(
                        "Introduce el precio estimado/manual (€):",
                        min_value=0.0,
                        value=default_val,
                        step=0.5
                    )

            with col_es_btn:
                st.write(" ")
                st.link_button("👉 Abrir en Cardmarket (Filtro ES + NM)", cm_url)

            set_info_str = f"{set_name} ({release_year}) - Rareza: {rarity_label} [{region_label}]"
            if st.button("⭐ Guardar / Actualizar en Favoritos"):
                if final_price_to_save > 0:
                    agregar_a_favoritos(selected_id, selected_name, final_price_to_save, img_url, set_info_str)
                    st.toast(f"¡Guardada con el precio de {final_price_to_save}€!", icon="⭐")
                else:
                    st.error("Introduce un precio mayor a 0€ para guardar.")

            if cm_data:
                st.subheader("Evolución General del Mercado (€)")
                chart_data = {
                    "30 Días": cm_data.get('avg30', 0) or cm_data.get('avg30-holo', 0),
                    "7 Días": cm_data.get('avg7', 0) or cm_data.get('avg7-holo', 0),
                    "1 Día": cm_data.get('avg1', 0) or cm_data.get('avg1-holo', 0),
                    "Tendencia": trend
                }
                st.line_chart(chart_data)

        else:
            st.error(f"No se encontraron cartas registradas para '{search_term}'.")

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

        st.caption("🟢 Cartas ordenadas automáticamente de **más cara a más barata**.")

        for card_id, data in favoritos_ordenados:
            with st.expander(f"💰 {data['precio_ultimo']} € — ⭐ {data['nombre']} ({card_id.upper()})"):
                col_img, col_det, col_hist = st.columns([1, 2, 2])
                
                with col_img:
                    if data.get("imagen"):
                        st.image(data["imagen"], width=130)

                with col_det:
                    if data.get("set_info"):
                        st.caption(f"📦 **Info:** {data['set_info']}")
                        
                    st.write(f"**Precio inicial guardado:** {data['precio_inicial']} €")
                    st.caption(f"Fecha: {data['fecha_inicial']}")
                    
                    st.write(f"**Último precio registrado:** {data['precio_ultimo']} €")
                    st.caption(f"Última revisión: {data['fecha_ultima']}")

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
                    st.write("**Historial registrado:**")
                    for reg in reversed(data.get("historial", [])):
                        st.write(f"• `{reg['fecha']}`: **{reg['precio']} €**")
