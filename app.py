import streamlit as st
import pandas as pd
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
    with st.spinner("Chargement des données depuis data.gouv.fr…"):
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

df = load_data()

# ── Sidebar — Filters ──────────────────────────────────────────────────────────
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/c/c3/Flag_of_France.svg", width=60)
st.sidebar.title("🔍 Filtres")

# Region
regions = sorted(df["reg_nom"].dropna().unique())
selected_regions = st.sidebar.multiselect("Région", regions, placeholder="Toutes les régions")

# Department (dynamic based on region selection)
if selected_regions:
    dep_options = sorted(df[df["reg_nom"].isin(selected_regions)]["dep_nom"].dropna().unique())
else:
    dep_options = sorted(df["dep_nom"].dropna().unique())
selected_deps = st.sidebar.multiselect("Département", dep_options, placeholder="Tous les départements")

# Equipment family
familles = sorted(df["equip_type_famille"].dropna().unique())
selected_familles = st.sidebar.multiselect("Famille d'équipement", familles, placeholder="Toutes")

# Sport
all_sports = (
    df["aps_name"].dropna().str.split(",").explode().str.strip().unique()
)
sports_sorted = sorted(set(all_sports))
selected_sport = st.sidebar.selectbox("Sport pratiqué", ["Tous"] + sports_sorted)

# Indoor / outdoor
nature_options = df["equip_nature"].dropna().unique().tolist()
selected_nature = st.sidebar.multiselect("Nature (intérieur/découvert)", nature_options, placeholder="Toutes")

# ── Apply filters ──────────────────────────────────────────────────────────────
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

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🏟️ Équipements Sportifs en France")
st.caption("Source : Recensement des Équipements Sportifs — data.gouv.fr")

# ── KPI cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Équipements", f"{len(filtered):,}")
k2.metric("Installations", f"{filtered['inst_numero'].nunique():,}")
k3.metric("Communes", f"{filtered['new_name'].nunique():,}")
k4.metric("Types d'équipements", f"{filtered['equip_type_name'].nunique():,}")

st.divider()

# ── Layout: map + top types ────────────────────────────────────────────────────
col_map, col_chart = st.columns([3, 2])

with col_map:
    st.subheader("📍 Carte des équipements")
    map_data = filtered[["lat", "lon", "equip_nom", "equip_type_famille", "inst_nom"]].dropna(subset=["lat", "lon"])
    sample_size = min(8000, len(map_data))
    map_sample = map_data.sample(sample_size, random_state=42) if len(map_data) > sample_size else map_data

    if not map_sample.empty:
        fig_map = px.scatter_map(
            map_sample,
            lat="lat",
            lon="lon",
            hover_name="equip_nom",
            hover_data={"equip_type_famille": True, "inst_nom": True, "lat": False, "lon": False},
            color="equip_type_famille",
            zoom=5,
            height=500,
            map_style="carto-positron",
        )
        fig_map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, showlegend=False)
        st.plotly_chart(fig_map, width="stretch")
        if len(map_data) > sample_size:
            st.caption(f"Affichage d'un échantillon de {sample_size:,} équipements sur {len(map_data):,}")
    else:
        st.info("Aucun équipement géolocalisé pour cette sélection.")

with col_chart:
    st.subheader("🏅 Top types d'équipements")
    type_counts = (
        filtered["equip_type_name"]
        .value_counts()
        .head(20)
        .reset_index()
    )
    type_counts.columns = ["Type", "Nombre"]
    fig_types = px.bar(
        type_counts,
        x="Nombre",
        y="Type",
        orientation="h",
        height=500,
        color="Nombre",
        color_continuous_scale="Blues",
    )
    fig_types.update_layout(
        yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )
    st.plotly_chart(fig_types, width="stretch")

st.divider()

# ── Row 2: by region + by sport ───────────────────────────────────────────────
col_reg, col_sport = st.columns(2)

with col_reg:
    st.subheader("🗺️ Équipements par région")
    reg_counts = (
        filtered["reg_nom"]
        .value_counts()
        .reset_index()
    )
    reg_counts.columns = ["Région", "Nombre"]
    fig_reg = px.bar(
        reg_counts,
        x="Région",
        y="Nombre",
        color="Nombre",
        color_continuous_scale="Teal",
    )
    fig_reg.update_layout(
        xaxis_tickangle=-40,
        coloraxis_showscale=False,
        margin={"t": 10},
    )
    st.plotly_chart(fig_reg, width="stretch")

with col_sport:
    st.subheader("⚽ Top 20 sports pratiqués")
    sport_counts = (
        filtered["aps_name"]
        .dropna()
        .str.split(",")
        .explode()
        .str.strip()
        .value_counts()
        .head(20)
        .reset_index()
    )
    sport_counts.columns = ["Sport", "Nombre"]
    fig_sport = px.bar(
        sport_counts,
        x="Sport",
        y="Nombre",
        color="Nombre",
        color_continuous_scale="Purples",
    )
    fig_sport.update_layout(
        xaxis_tickangle=-40,
        coloraxis_showscale=False,
        margin={"t": 10},
    )
    st.plotly_chart(fig_sport, width="stretch")

st.divider()

# ── Row 3: nature + accessibility ─────────────────────────────────────────────
col_nat, col_bool = st.columns(2)

with col_nat:
    st.subheader("🏠 Intérieur vs Découvert")
    nature_counts = filtered["equip_nature"].value_counts().reset_index()
    nature_counts.columns = ["Nature", "Nombre"]
    fig_nat = px.pie(
        nature_counts,
        names="Nature",
        values="Nombre",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
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
    fig_bool = px.bar(
        rates_df,
        x="Caractéristique",
        y="% équipements",
        color="% équipements",
        color_continuous_scale="Greens",
        range_y=[0, 100],
        text="% équipements",
    )
    fig_bool.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_bool.update_layout(coloraxis_showscale=False, margin={"t": 10})
    st.plotly_chart(fig_bool, width="stretch")

st.divider()

# ── Summary table ──────────────────────────────────────────────────────────────
st.subheader("📊 Tableau récapitulatif — types d'équipements")
total = len(filtered)
summary = (
    filtered["equip_type_name"]
    .value_counts()
    .reset_index()
)
summary.columns = ["Type d'équipement", "Nombre"]
summary["% du total"] = (summary["Nombre"] / total * 100).round(2)
summary.index = range(1, len(summary) + 1)
summary.index.name = "Rang"
st.dataframe(
    summary,
    width="stretch",
    column_config={
        "Nombre": st.column_config.NumberColumn(format="%d"),
        "% du total": st.column_config.ProgressColumn(
            format="%.2f%%", min_value=0, max_value=summary["% du total"].max()
        ),
    },
)

st.divider()

# ── Raw data explorer ──────────────────────────────────────────────────────────
with st.expander("🔎 Explorer les données brutes"):
    cols_to_show = [
        "inst_nom", "equip_nom", "equip_type_famille", "equip_type_name",
        "aps_name", "equip_nature", "equip_sol", "new_name", "dep_nom",
        "reg_nom", "inst_acc_handi_bool", "equip_eclair",
    ]
    cols_available = [c for c in cols_to_show if c in filtered.columns]
    st.dataframe(filtered[cols_available].reset_index(drop=True), width="stretch", height=400)
    st.caption(f"{len(filtered):,} équipements affichés")
