import plotly.express as px
import streamlit
import pandas as p

from sizing_tool.gantt_calculator import (
    get_new_milestones_dates,
    get_milestones_dates,
    load_gantt_calculator_params
    )

__version__ = 1.0



try:
    streamlit.set_option('deprecation.showfileUploaderEncoding', False)
except:
    pass


def convert_time_delta_to_months(x):
    return x.days*12./365.
def convert_time_delta_to_weeks(x):
    return x.days/7



streamlit.title("Gantt calculator")
status = streamlit.empty()
CommercialLaunchDate = streamlit.sidebar.date_input("CommercialLaunchDate", value=p.to_datetime('01/05/2023', format='%d/%m/%Y'))
zone = streamlit.sidebar.selectbox("Zone", ["EUR", "E2A", "ADS", "ADN", "CHN", "MSA"])
DesignType = streamlit.sidebar.selectbox("DesignType", ["CLEAN SHEET", "REFRESH", "EXTENSION"])
BaliseType = streamlit.sidebar.selectbox("BaliseType", ["B+M", "M"])
GanttCategory = streamlit.sidebar.selectbox("GanttCategory", ["WINTER", "SUMMER", "A/S"])
LaunchScope = streamlit.sidebar.selectbox("LaunchScope", ["WW", "Local"])
ProcessType = streamlit.sidebar.selectbox("ProcessType", ["MANU", "C3M"])
MoldTechno = streamlit.sidebar.selectbox("MoldTechno", ["EI", "C3M", "PA/EB/TR"])
TdGMain_Loop1 = streamlit.sidebar.number_input("TdG Loop1", min_value=0, max_value=10, value=1)
TdGMain_Loop2 = streamlit.sidebar.number_input("TdG Loop2", min_value=0, max_value=10, value=1)
Declis = streamlit.sidebar.number_input("Nbr of Indus", min_value=0, max_value=200, value=10)
CAIs_pourcents = streamlit.sidebar.number_input("% of CAIs at the LC", min_value=0, max_value=100, value=100)
is_full_regulatory_test = streamlit.sidebar.checkbox("Regulatory tests include DOT or CCC", True)
is_labelling_mandatory = streamlit.sidebar.checkbox("Include 4 month constraint for Labelling", True)
Mold_entries_per_week_in_G2LC = streamlit.sidebar.number_input("Mold_entries_per_week_in_G2LC", min_value=1.0, max_value=5.0, value=1., step=0.1)

params_filename = streamlit.file_uploader('Params file:', type="xlsx")


if params_filename:
    gc_params = p.read_excel(params_filename,
        sheet_name="params",
        keep_default_na=False,
        na_values=[""],
        engine="openpyxl"
    )

    test_project = p.Series({'zone': zone,
     'project_name':"",
     'DesignType':DesignType,
     'BaliseType': BaliseType,
     'CommercialLaunchDate': CommercialLaunchDate, #p.to_datetime('01/05/2023', format='%m/%d/%Y'),
     'GanttCategory': GanttCategory,
     'LaunchScope': LaunchScope,
     'ProcessType': ProcessType,
     'MoldTechno': MoldTechno,
     'TdGMain_Loop1':TdGMain_Loop1,
     'TdGMain_Loop2':TdGMain_Loop2,
     'TdGSec_Loop1':0,
     'TdGSec_Loop2':0,
     'TdG_MAT_Loop2':0,
     'Declis_pourcents':CAIs_pourcents,
     'Declis': Declis*CAIs_pourcents/100.,
     'MoulistStudies':Declis*CAIs_pourcents/100., # Consider same number than decli to simplify
     'MultiSourcedCai':0,
     'Mold_entries_per_week_in_G2LC': Mold_entries_per_week_in_G2LC,
     })

    B0, B1, B2, B3, G0, G1, G2, LC = get_milestones_dates(gc_params, test_project)
    new_B0, new_B1, new_B2, new_B3, new_G0, new_G1, new_G2, LC = get_new_milestones_dates(gc_params, test_project, status=status, is_full_regulatory_test=is_full_regulatory_test, is_labelling_mandatory=is_labelling_mandatory, verbose=True)

    milestones_std_GC = p.Series({
        "B0":str(B0),
        "B1":str(B1),
        "B2":str(B2),
        "G0":str(G0),
        "G1":str(G1),
        "G2":str(G2)
        })
    milestones_new_GC = p.Series({
        "B0":str(new_B0),
        "B1":str(new_B1),
        "B2":str(new_B2),
        "G0":str(new_G0),
        "G1":str(new_G1),
        "G2":str(new_G2)
        })

    milestones_df = p.concat([milestones_std_GC.rename("standard Gantt"), milestones_new_GC.rename("new Gantt")], axis=1, sort=False)
    streamlit.write(milestones_df)


    def get_durations(B0, B1, B2, B3, G0, G1, G2, LC):
        return p.Series({
        "G2-LC":convert_time_delta_to_months(LC-G2),
        "G1-G2":convert_time_delta_to_months(G2-G1),
        "G0-G1":convert_time_delta_to_months(G1-G0),
        "B1-B2":convert_time_delta_to_months(B2-B1),
        "B0-B1":convert_time_delta_to_months(B1-B0),
        })

    std_durations = p.DataFrame(get_durations(B0, B1, B2, B3, G0, G1, G2, LC))
    std_durations.loc[:,'Gantt'] = "Standard"
    new_durations = p.DataFrame(get_durations(new_B0, new_B1, new_B2, new_B3, new_G0, new_G1, new_G2, LC))
    new_durations.loc[:,'Gantt'] = "NEW"

    plot_df = p.concat([std_durations, new_durations], axis=0, sort=False).reset_index()
    plot_df.columns = ["Project phase", "duration", "Gantt"]
    #streamlit.bar_chart(plot_df)
    fig = px.bar(plot_df, x="Project phase", y="duration", color="Gantt", orientation='v', barmode='group', text="duration") #, color=color, text=color)
    fig.update_traces(texttemplate='%{text:.1f} mois', textposition='outside')
    streamlit.plotly_chart(fig)
