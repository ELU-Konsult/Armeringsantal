import streamlit as st
import pandas as pd
import xml.etree.ElementTree as et
from io import StringIO
import csv
import ifcopenshell as ifc
import ifcopenshell.util.pset
from ifcopenshell import util

# st.set_page_config(layout="wide")


def csv_to_df(file):
    stringio = StringIO(file.getvalue().decode("utf-8"))
    csv.register_dialect("semicolon", delimiter=";")
    reader = csv.reader(stringio, dialect="semicolon")
    mark_sum = {}

    for row in reader:
        try:
            mark = int(row[0])
        except:
            mark = 0
            continue
        if mark > 0:  # Bara rader med data
            n = int(row[1])

            if mark in mark_sum:
                mark_sum[mark] += n
            else:
                mark_sum[mark] = n

    df = pd.DataFrame(mark_sum.items(), columns=["Littera", file.name])
    df["Littera"] = df["Littera"].astype(str)
    return df


def xml_to_df(file):
    stringio = StringIO(file.getvalue().decode("utf-8"))
    element_tree = et.parse(stringio)
    root = element_tree.getroot()

    # Initialize lists to store extracted data
    mark_sum = {}

    # Extract data from each B2aPageRow
    for b2a_row in root.findall(".//B2aPageRow"):
        mark = b2a_row.find(".//Litt").text
        n_grps = b2a_row.find(".//NoGrps").text
        bars_per_grp = b2a_row.find(".//NoStpGrp").text
        mark_sum[mark] = int(n_grps) * int(bars_per_grp)

    df = pd.DataFrame(mark_sum.items(), columns=["Littera", file.name])
    df["Littera"] = df["Littera"].astype(str)
    return df


def create_rebar_dict_Tekla(psets):
    try:
        rebar_pset = psets["Tekla Reinforcement - Bending List"]
        mark = rebar_pset["Group position number"]
        props = [
            ("Antal", "Number of bars in group"),
            ("Kvalitet", "Grade"),
            ("Diameter", "Size"),
            ("Bockningstyp", "Shape"),
        ]
        dict = {}

        for p in props:
            dict[p[0]] = rebar_pset[p[1]]

        return mark, dict

    except:
        return None


def ifc_to_df(path):
    stringio = StringIO(file.getvalue().decode("utf-8"))
    ifc_file = ifc.file.from_string(stringio.read())
    rebar = ifc_file.by_type("IfcReinforcingBar")
    rebar_dict = {}
    rvt = "Revit" in ifc_file.by_type("IFCAPPLICATION")[0]

    for bar in rebar:
        pset = ifcopenshell.util.element.get_psets(bar)
        if rvt:
            mark, dict = create_rebar_dict_RVT(pset)
        else:
            mark, dict = create_rebar_dict_Tekla(pset)
        if mark in rebar_dict:
            n_prev = rebar_dict[mark].pop("Antal")
            n_new = dict.pop("Antal")
            if rebar_dict[mark] == dict:
                rebar_dict[mark]["Antal"] = n_prev + n_new
            else:
                # raise Exception(
                #     f"{mark} has conflicting values: {dict} , {rebar_dict[mark]}"
                # )
                rebar_dict[mark]["Antal"] = n_prev + n_new  # temp
        else:
            rebar_dict[mark] = dict
    df = pd.DataFrame(rebar_dict).transpose()
    return df


def check_equality(df):
    number_columns = df.drop("Littera", axis=1)
    equal = number_columns.eq(number_columns.iloc[:, 0], axis=0)
    all_equal = equal.transpose().all().transpose()
    all_equal.name = "Lika"
    return df.join(all_equal, how="left")


def highlight_diff(s):  # formattering av rader som skiljer sig
    return (
        ["background-color: lightgreen"] * len(s)
        if s.Lika
        else ["background-color: salmon"] * len(s)
    )


ifc_default_tekla = {
    "conf_quantity": "Tekla Reinforcement - Bending List / Number of bars in group",
    "conf_diam": "Tekla Reinforcement - Bending List / Size",
    "conf_shape": "Tekla Reinforcement - Bending List / Shape",
    "conf_mark": "Tekla Reinforcement - Bending List / Group position number",
    "conf_material": "Tekla Reinforcement - Bending List / Grade",
}
# Create an empty DataFrame with column names and data types
schema = {"Littera": "str"}
df_main = pd.DataFrame(columns=schema.keys()).astype(schema)


sidebar = st.sidebar

sidebar.header("Konfiguration IFC")
sidebar.write("Format: pset / attribut")
conf_quantity = sidebar.text_input(
    "Antal", value=st.session_state.ifc_config["conf_quantity"]
)
conf_diam = sidebar.text_input(
    "Diameter", value=st.session_state.ifc_config["conf_diam"]
)
conf_shape = sidebar.text_input(
    "Bockningstyp", value=st.session_state.ifc_config["conf_shape"]
)
conf_mark = sidebar.text_input(
    "Littera", value=st.session_state.ifc_config["conf_mark"]
)
conf_material = sidebar.text_input(
    "Kvalitet", value=st.session_state.ifc_config["conf_material"]
)
if sidebar.button("Spara"):
    st.session_state.ifc_config = {
        "conf_quantity": conf_quantity,
        "conf_diam": conf_diam,
        "conf_shape": conf_shape,
        "conf_mark": conf_mark,
        "conf_material": conf_material,
    }
    st.rerun()
if sidebar.button("Default"):
    st.session_state.ifc_config = ifc_default_tekla
    st.rerun()

# fixa formatering
# df_main = df_main.astype(int, errors="ignore")
# df_main["Littera"] = df_main["Littera"].astype(str)

if "ifc_config" not in st.session_state:
    st.session_state.ifc_config = ifc_default_tekla

st.session_state.ifc_config

# Huvudinnehållet i appen
st.title("Kontroll armeringsantal")
st.write(
    """Ladda upp dina filer för att jämföra nedan.  
         Tillåtna format: CSV, XML, IFC """
)

header = st.container()
left, right = header.columns(2)
file_left = left.file_uploader("Ladda upp fil", accept_multiple_files=False, key=left)
file_right = right.file_uploader(
    "Ladda upp fil", accept_multiple_files=False, key=right
)


# Visa de uppladdade filerna
def upload_file(file, side):
    if file.name[-3:].lower() == "csv":
        csv_df = csv_to_df(file)
        df_main = df_main.merge(csv_df, how="outer", on="Littera")
    elif file.name[-3:].lower() == "xml":
        xml_df = xml_to_df(file)
        df_main = df_main.merge(xml_df, how="outer", on="Littera")
    elif file.name[-3:].lower() == "ifc":
        ifc_df = ifc_to_df(file)
        st.write(ifc_df)
    if file_left and file_right:
        df_main = check_equality(df_main)


if file_left:
    upload_file(file_left, "left")
if file_right:
    upload_file(file_right, "right")

result = st.container()

result.dataframe(
    df_main.sort_values(by=["Littera"]).style.apply(highlight_diff, axis=1),
    hide_index=True,
)
# st.dataframe(styled_df, hide_index=True, column_config={"B": None}) # dölj kolumn

result.download_button(
    "Ladda ner resultat",
    data=pd.DataFrame.to_csv(df_main, index=False),
    mime="text/csv",
)

# Kör appen med: streamlit run app.py
