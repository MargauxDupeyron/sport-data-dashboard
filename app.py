import re
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FindSport — Équipements Sportifs France",
    page_icon="🏟️",
    layout="wide",
)

# ── Load data ──────────────────────────────────────────────────────────────────
DATA_URL = (
    "https://equipements.sports.gouv.fr/api/explore/v2.1/"
    "catalog/datasets/data-es/exports/csv?delimiter=%3B"
)

@st.cache_data(ttl=86400)  # cache for 24h — data is updated daily
def load_data():
    df = pd.read_csv(DATA_URL, sep=";", low_memory=False)
    # Parse coordinates
    coords = df["equip_coordonnees"].dropna().str.split(",", expand=True)
    coords.columns = ["lat", "lon"]
    coords = coords.apply(pd.to_numeric, errors="coerce")
    df["lat"] = coords["lat"]
    df["lon"] = coords["lon"]
    # Keep only metropolitan France
    mask = df["lat"].between(41, 52) & df["lon"].between(-6, 10)
    df.loc[~mask, ["lat", "lon"]] = None
    return df

@st.cache_data
def get_sports_list(df):
    return sorted(
        df["aps_name"].dropna().str.split(",").explode().str.strip().unique()
    )

# Category → lowercase keywords for matching sport names
_CATEGORY_KEYWORDS = {
    "Athlétisme & Courses": [
        "course sur le plat", "course sur piste", "course et marche",
        "marathon", "marche nordique", "marche ", "lancer", " saut",
        "épreuves combin", "cross country", "duathlon", "triathlon", "pentathlon",
    ],
    "Cyclisme": ["cycl", "bicross", "bmx", "vtt"],
    "Danse & Expression": [
        "danse", "ballet", "expression gymnique", "expression libre",
        "twirling", "cheerleading", "swing",
    ],
    "Équitation": [
        "équitation", "dressage", "saut d'obstacle", "concours complet",
        "horse-ball", "polo-v", "équestre", "attelage", "rodéo",
    ],
    "Escalade & Montagne": ["escalade", "alpinisme", "via ferrata", "spéléo", "canyonisme"],
    "Glisse sur neige & glace": [
        "ski ", "snowboard", "surf des neiges", "luge", "bobsleigh",
        "curling", "patinage", "ballet sur glace", "ringuette",
    ],
    "Glisse urbaine": ["roller", "skate", "planche à roulettes"],
    "Gymnastique": ["gymn", "trampoline", "tumbling", "double mini", "acrobatique"],
    "Musculation & Force": ["haltéro", "muscul", "culturisme", "force athlét"],
    "Natation & Sports aquatiques": [
        "natation", "water-polo", "plongeon", "synchronis",
        "nage", "aquagym", "baignade", "plong",
    ],
    "Plein air & Randonnée": ["randonn", "raquette à neige", "cross canin", "orientation"],
    "Sports aériens": [
        "parachut", "parapente", "deltaplane", "vol à voile", "voltige",
        "aéro", "planeur", "giraviation", "cerf volant", "ascensionnel", "aérostat",
    ],
    "Sports collectifs": [
        "basket", "handball", "volley", "football", "rugby",
        "hockey", "baseball", "softball", "cricket", "beach soccer", "futsal",
    ],
    "Sports de combat": [
        "boxe", "karaté", "taekwondo", "kick boxing", "muay", "savate",
        "full contact", "judo", "jujitsu", "lutte", "sambo", "sumo",
        "escrime", "kendo", "aïkido", "aikido", "arts martiaux", "bâton", "canne",
    ],
    "Sports de raquette": ["tennis", "badminton", "squash", "padel", "racquetball", "pickleball"],
    "Sports de tir": ["tir ", "arbalète", "carabine", "pistolet", "cible", "plateaux", "fosse", "compak"],
    "Sports mécaniques": ["karting", "motocross", "motocycl", "moto ", "automobile", "enduro", "quad", "motonautisme"],
    "Sports nautiques": [
        "aviron", "canoë", "kayak", "voile", "surf", "planche à voile",
        "ski nautique", "pirogue", "stand up", "wave-ski", "raft",
        "joutes", "sauvetage c", "merathon",
    ],
    "Activités de forme & bien-être": ["activités de forme", "multisports", "tai chi", "chi gong"],
    "Jeux & Divers": [
        "billard", "boules", "bowling", "pétanque", "jeu de",
        "échecs", "crocket", "paintball", "pêche", "longue paume", "courte paume",
    ],
}

@st.cache_data
def get_sports_in_category(df, category):
    all_sports = sorted(df["aps_name"].dropna().str.split(",").explode().str.strip().unique())
    if category == "Toutes les catégories":
        return all_sports
    keywords = _CATEGORY_KEYWORDS.get(category, [])
    return [s for s in all_sports if any(kw in s.lower() for kw in keywords)] or all_sports

def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorised haversine — returns distance in km."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))

with st.spinner("Chargement des données depuis data.gouv.fr…"):
    df = load_data()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_dashboard, tab_analyse = st.tabs(["📊 Tableau de bord", "🔍 Analyse par discipline & lieu"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.title("🏟️ Équipements Sportifs en France")
    st.caption("Source : Recensement des Équipements Sportifs — data.gouv.fr")

    # ── Sidebar filters (only active on this tab) ──────────────────────────────
    with st.sidebar:
        st.title("🔍 Filtres — Tableau de bord")

        regions = sorted(df["reg_nom"].dropna().unique())
        selected_regions = st.multiselect("Région", regions, placeholder="Toutes les régions")

        if selected_regions:
            dep_options = sorted(df[df["reg_nom"].isin(selected_regions)]["dep_nom"].dropna().unique())
        else:
            dep_options = sorted(df["dep_nom"].dropna().unique())
        selected_deps = st.multiselect("Département", dep_options, placeholder="Tous les départements")

        familles = sorted(df["equip_type_famille"].dropna().unique())
        selected_familles = st.multiselect("Famille d'équipement", familles, placeholder="Toutes")

        sports_sorted = get_sports_list(df)
        selected_sport = st.selectbox("Sport pratiqué", ["Tous"] + sports_sorted)

        nature_options = df["equip_nature"].dropna().unique().tolist()
        selected_nature = st.multiselect("Nature (intérieur/découvert)", nature_options, placeholder="Toutes")

    # ── Apply filters ──────────────────────────────────────────────────────────
    filtered = df.copy()
    if selected_regions:
        filtered = filtered[filtered["reg_nom"].isin(selected_regions)]
    if selected_deps:
        filtered = filtered[filtered["dep_nom"].isin(selected_deps)]
    if selected_familles:
        filtered = filtered[filtered["equip_type_famille"].isin(selected_familles)]
    if selected_sport != "Tous":
        filtered = filtered[filtered["aps_name"].fillna("").str.contains(selected_sport, case=False)]
    if selected_nature:
        filtered = filtered[filtered["equip_nature"].isin(selected_nature)]

    # ── KPI cards ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Équipements", f"{len(filtered):,}")
    k2.metric("Installations", f"{filtered['inst_numero'].nunique():,}")
    k3.metric("Communes", f"{filtered['new_name'].nunique():,}")
    k4.metric("Types d'équipements", f"{filtered['equip_type_name'].nunique():,}")

    st.divider()

    # ── Map + top types ────────────────────────────────────────────────────────
    col_map, col_chart = st.columns([3, 2])

    with col_map:
        st.subheader("📍 Carte des équipements")
        map_data = filtered[["lat", "lon", "equip_nom", "equip_type_famille", "inst_nom"]].dropna(subset=["lat", "lon"])
        sample_size = min(8000, len(map_data))
        map_sample = map_data.sample(sample_size, random_state=42) if len(map_data) > sample_size else map_data

        if not map_sample.empty:
            fig_map = px.scatter_map(
                map_sample, lat="lat", lon="lon",
                hover_name="equip_nom",
                hover_data={"equip_type_famille": True, "inst_nom": True, "lat": False, "lon": False},
                color="equip_type_famille", zoom=5, height=500, map_style="carto-positron",
            )
            fig_map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False)
            st.plotly_chart(fig_map, width="stretch")
            if len(map_data) > sample_size:
                st.caption(f"Échantillon de {sample_size:,} / {len(map_data):,} équipements")
        else:
            st.info("Aucun équipement géolocalisé pour cette sélection.")

    with col_chart:
        st.subheader("🏅 Top types d'équipements")
        type_counts = filtered["equip_type_name"].value_counts().head(20).reset_index()
        type_counts.columns = ["Type", "Nombre"]
        fig_types = px.bar(type_counts, x="Nombre", y="Type", orientation="h", height=500,
                           color="Nombre", color_continuous_scale="Blues")
        fig_types.update_layout(yaxis={"categoryorder": "total ascending"},
                                coloraxis_showscale=False, margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig_types, width="stretch")

    st.divider()

    col_reg, col_sport2 = st.columns(2)

    with col_reg:
        st.subheader("🗺️ Équipements par région")
        reg_counts = filtered["reg_nom"].value_counts().reset_index()
        reg_counts.columns = ["Région", "Nombre"]
        fig_reg = px.bar(reg_counts, x="Région", y="Nombre", color="Nombre", color_continuous_scale="Teal")
        fig_reg.update_layout(xaxis_tickangle=-40, coloraxis_showscale=False, margin={"t": 10})
        st.plotly_chart(fig_reg, width="stretch")

    with col_sport2:
        st.subheader("⚽ Top 20 sports pratiqués")
        sport_counts = (filtered["aps_name"].dropna().str.split(",").explode().str.strip()
                        .value_counts().head(20).reset_index())
        sport_counts.columns = ["Sport", "Nombre"]
        fig_sport = px.bar(sport_counts, x="Sport", y="Nombre", color="Nombre", color_continuous_scale="Purples")
        fig_sport.update_layout(xaxis_tickangle=-40, coloraxis_showscale=False, margin={"t": 10})
        st.plotly_chart(fig_sport, width="stretch")

    st.divider()

    col_nat, col_bool = st.columns(2)

    with col_nat:
        st.subheader("🏠 Intérieur vs Découvert")
        nature_counts = filtered["equip_nature"].value_counts().reset_index()
        nature_counts.columns = ["Nature", "Nombre"]
        fig_nat = px.pie(nature_counts, names="Nature", values="Nombre", hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Set2)
        fig_nat.update_layout(margin={"t": 10})
        st.plotly_chart(fig_nat, width="stretch")

    with col_bool:
        st.subheader("♿ Caractéristiques clés")
        bool_cols = {
            "Accessible PMR": "inst_acc_handi_bool",
            "Éclairage artificiel": "equip_eclair",
            "Ouvert au public": "equip_ouv_public_bool",
            "Accès libre": "equip_acc_libre",
        }
        rates = {}
        for label, col in bool_cols.items():
            if col in filtered.columns:
                s = filtered[col].astype(str).str.lower()
                rates[label] = round(s.isin(["true", "1", "oui", "yes"]).mean() * 100, 1)
        rates_df = pd.DataFrame({"Caractéristique": rates.keys(), "% équipements": rates.values()})
        fig_bool = px.bar(rates_df, x="Caractéristique", y="% équipements", color="% équipements",
                          color_continuous_scale="Greens", range_y=[0, 100], text="% équipements")
        fig_bool.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_bool.update_layout(coloraxis_showscale=False, margin={"t": 10})
        st.plotly_chart(fig_bool, width="stretch")

    st.divider()

    st.subheader("📊 Tableau récapitulatif — types d'équipements")
    total = len(filtered)
    summary = filtered["equip_type_name"].value_counts().reset_index()
    summary.columns = ["Type d'équipement", "Nombre"]
    summary["% du total"] = (summary["Nombre"] / total * 100).round(2)
    summary.index = range(1, len(summary) + 1)
    summary.index.name = "Rang"
    st.dataframe(summary, width="stretch", column_config={
        "Nombre": st.column_config.NumberColumn(format="%d"),
        "% du total": st.column_config.ProgressColumn(
            format="%.2f%%", min_value=0, max_value=summary["% du total"].max()),
    })

    st.divider()

    with st.expander("🔎 Explorer les données brutes"):
        cols_to_show = ["inst_nom", "equip_nom", "equip_type_famille", "equip_type_name",
                        "aps_name", "equip_nature", "equip_sol", "new_name", "dep_nom",
                        "reg_nom", "inst_acc_handi_bool", "equip_eclair"]
        cols_available = [c for c in cols_to_show if c in filtered.columns]
        st.dataframe(filtered[cols_available].reset_index(drop=True), width="stretch", height=400)
        st.caption(f"{len(filtered):,} équipements affichés")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ANALYSE PAR DISCIPLINE & LIEU
# ══════════════════════════════════════════════════════════════════════════════
with tab_analyse:
    st.title("🔍 Analyse par discipline & lieu")
    st.caption("Sélectionnez une discipline et une ville pour explorer les équipements et la concurrence.")

    # ── Filters ───────────────────────────────────────────────────────────────
    selected_categories = st.multiselect(
        "🏆 Catégorie", sorted(_CATEGORY_KEYWORDS.keys()),
        placeholder="Toutes les catégories"
    )

    col_f1, col_f2 = st.columns(2)

    with col_f1:
        if selected_categories:
            sports_set = set()
            for cat in selected_categories:
                sports_set.update(get_sports_in_category(df, cat))
            sports_in_cat = sorted(sports_set)
        else:
            sports_in_cat = get_sports_list(df)

        selected_disciplines = st.multiselect(
            "🏃 Discipline", sports_in_cat,
            placeholder="Toutes les disciplines"
        )

    # Filter by disciplines to get relevant cities
    if selected_disciplines:
        pattern = "|".join(re.escape(d) for d in selected_disciplines)
        disc_df = df[df["aps_name"].fillna("").str.contains(pattern, case=False)]
    else:
        disc_df = df[df["aps_name"].fillna("").str.len() > 0]

    with col_f2:
        cities = sorted(disc_df["new_name"].dropna().unique())
        saved_city = st.session_state.get("selected_city")
        default_index = cities.index(saved_city) if saved_city in cities else 0
        selected_city = st.selectbox("🏙️ Commune", cities if cities else ["Aucune commune trouvée"], index=default_index)
        st.session_state["selected_city"] = selected_city

    if not cities:
        st.warning("Aucune commune trouvée pour cette sélection.")
        st.stop()

    # Radius filter
    radius_km = st.slider("Rayon de recherche autour de la commune (km)", min_value=5, max_value=100, value=30, step=5)

    st.divider()

    # ── Data for selected city + discipline ────────────────────────────────────
    city_disc_df = disc_df[disc_df["new_name"] == selected_city].copy()
    city_disc_df = city_disc_df.dropna(subset=["lat", "lon"])

    # ── Map + detail panel ─────────────────────────────────────────────────────
    col_map2, col_detail = st.columns([3, 2])

    with col_map2:
        disc_label = ", ".join(selected_disciplines) if selected_disciplines else "Toutes disciplines"
        st.subheader(f"📍 {disc_label} à {selected_city}")

        if city_disc_df.empty:
            st.info("Aucun équipement géolocalisé pour cette sélection.")
        else:
            # Build map data with index stored in customdata for click retrieval
            city_disc_df = city_disc_df.reset_index(drop=True)
            city_disc_df["_idx"] = city_disc_df.index

            fig2 = px.scatter_map(
                city_disc_df,
                lat="lat", lon="lon",
                hover_name="equip_nom",
                hover_data={
                    "equip_type_name": True,
                    "inst_nom": True,
                    "inst_adresse": True,
                    "_idx": False,
                    "lat": False,
                    "lon": False,
                },
                custom_data=["_idx"],
                color="equip_type_name",
                size_max=12,
                zoom=12,
                height=520,
                map_style="carto-positron",
            )
            fig2.update_traces(marker={"size": 14})
            fig2.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=True,
                               legend={"title": "Type", "orientation": "h", "y": -0.05})

            event = st.plotly_chart(fig2, width="stretch", on_select="rerun", selection_mode="points", key="map2")

    with col_detail:
        st.subheader("ℹ️ Fiche équipement")

        selected_row = None

        # Retrieve clicked point
        if (not city_disc_df.empty
                and event
                and event.get("selection")
                and event["selection"].get("points")):
            point = event["selection"]["points"][0]
            idx = int(point["customdata"][0])
            selected_row = city_disc_df.iloc[idx]

        if selected_row is None:
            st.info("Cliquez sur un équipement sur la carte pour voir sa fiche.")
        else:
            # ── Equipment details ──────────────────────────────────────────────
            st.markdown(f"### {selected_row.get('equip_nom', 'N/A')}")
            st.markdown(f"**Installation :** {selected_row.get('inst_nom', 'N/A')}")
            st.markdown(f"**Adresse :** {selected_row.get('inst_adresse', 'N/A')}, {selected_row.get('inst_cp', '')} {selected_city}")
            st.markdown(f"**Type :** {selected_row.get('equip_type_name', 'N/A')}")
            st.markdown(f"**Nature :** {selected_row.get('equip_nature', 'N/A')} — Sol : {selected_row.get('equip_sol', 'N/A')}")

            pmr = str(selected_row.get("inst_acc_handi_bool", "")).lower() in ["true", "1"]
            eclairage = str(selected_row.get("equip_eclair", "")).lower() in ["true", "1"]
            public = str(selected_row.get("equip_ouv_public_bool", "")).lower() in ["true", "1"]
            libre = str(selected_row.get("equip_acc_libre", "")).lower() in ["true", "1"]

            badges = " | ".join(filter(None, [
                "♿ PMR" if pmr else None,
                "💡 Éclairé" if eclairage else None,
                "🔓 Ouvert au public" if public else None,
                "🆓 Accès libre" if libre else None,
            ]))
            if badges:
                st.markdown(f"**Équipements :** {badges}")

            st.divider()

            # ── Competitive analysis ───────────────────────────────────────────
            sel_lat = selected_row["lat"]
            sel_lon = selected_row["lon"]
            sel_equip_id = selected_row.get("equip_numero", None)

            # All same-discipline facilities with coordinates (excluding itself)
            if selected_disciplines:
                comp_pattern = "|".join(re.escape(d) for d in selected_disciplines)
                comp_mask = df["aps_name"].fillna("").str.contains(comp_pattern, case=False)
            else:
                comp_mask = df["aps_name"].fillna("").str.len() > 0
            comp_pool = df[comp_mask & df["lat"].notna() & df["lon"].notna()].copy()
            comp_pool = comp_pool[comp_pool["equip_numero"] != sel_equip_id]

            # Distance to each competitor
            comp_pool["distance_km"] = haversine_km(
                sel_lat, sel_lon,
                comp_pool["lat"].values, comp_pool["lon"].values
            )

            # In same city
            same_city = comp_pool[comp_pool["new_name"] == selected_city]
            # Within radius
            within_radius = comp_pool[comp_pool["distance_km"] <= radius_km].sort_values("distance_km")
            # Nearest 3
            nearest = within_radius.head(3)

            # KPIs
            c1, c2 = st.columns(2)
            c1.metric(f"Concurrents à {selected_city}", len(same_city))
            c2.metric(f"Dans un rayon de {radius_km} km", len(within_radius))

            st.divider()

            # Nearest competitors table
            if not nearest.empty:
                st.markdown("**📌 Les 3 plus proches concurrents**")
                for _, comp in nearest.iterrows():
                    dist = comp["distance_km"]
                    name = comp.get("equip_nom", "N/A")
                    city_c = comp.get("new_name", "N/A")
                    type_c = comp.get("equip_type_name", "N/A")
                    st.markdown(
                        f"- **{name}** — {city_c} · {type_c}  \n"
                        f"  📏 {dist:.1f} km"
                    )

            st.divider()

            # Distribution of competitors by type within radius
            if not within_radius.empty:
                st.markdown(f"**Types d'équipements dans {radius_km} km**")
                type_dist = within_radius["equip_type_name"].value_counts().head(8).reset_index()
                type_dist.columns = ["Type", "Nombre"]
                fig_comp = px.bar(type_dist, x="Nombre", y="Type", orientation="h",
                                  color="Nombre", color_continuous_scale="Reds", height=250)
                fig_comp.update_layout(coloraxis_showscale=False,
                                       margin={"r": 0, "t": 0, "l": 0, "b": 0},
                                       yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_comp, width="stretch")
