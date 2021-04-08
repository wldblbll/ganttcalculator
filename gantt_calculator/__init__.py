# coding: utf-8
import os
from math import ceil as arrondi_sup
import pandas as p
import datetime
import streamlit

__version__ = 1.0

# HARD CODED in GantCalculator
CPV_MOLD_CAPACITY_PER_WEEK = 2.5
NB_PLANTS = 2.5


###################################################################
# Reprise de la fonction "PlanProduitDonneesPourCalculJalons" :
###################################################################
def set_Design_Zone_for_gantt_calculator(zone_name):
    zone_name = str(zone_name).upper()
    if zone_name == "EUR":
        return "Europe"
    elif (
        zone_name == "JPK"
        or zone_name == "ASIA"
        or zone_name == "AIM"
        or zone_name == "E2A"
        or zone_name == "CHN"
    ):
        return "Asia"
    elif zone_name == "ADN" or zone_name == "NCA" or zone_name == "NA":
        return "NA"
    elif zone_name == "ADS":
        return "SA"
    elif zone_name == "MSA":
        return "MSA"
    else:
        print("[Gantt Calculator] Warning : unknow design zone : %s" % zone_name)
        return "UNKNOWN"


def set_TypeGantt(row):
    if row.DesignType == "EXTENSION":
        if row.TdGMain + row.TdGSec > 0:
            return "Extension - With Development"
        else:
            return "Extension - Without Development"
    elif row.DesignType in ["CLEAN SHEET", "REFRESH"]:
        if row.BaliseType == "B+M":
            return "B+M"
        elif (
            row.TdGMain_Loop2 + row.TdGSec_Loop2 + row.TdG_MAT_Loop2
        ) > 0:  # row.TdGLoop>1:
            return "Market (2-loops)"
        else:
            return "Market (1-loop)"
    elif row.DesignType == "INTERZONEBRIDGE":
        return "Passerelle"
    elif row.DesignType == "OFFTAKE" or row.DesignType == "IMPORT":
        return "Off-Take"
    print("[Gantt Calculator] warning : unknow Design Type : %s" % str(row.BaliseType))
    return ""


def set_Categorie(row):
    if (
        row.project_name.upper().count("STUD") > 0
        or row.project_name.upper().count("NORTH") > 0
    ):
        return "Cloute / Studded tire"
    elif row.GanttCategory.upper().count("WINTER") > 0:
        return "Winter"
    elif row.GanttCategory.upper().count("COMMERCIAL") > 0:
        return "Commercial"
    else:
        return "All season / summer / SUV"


def set_TechnoMoule(row):
    """
        Cette fonction a été simplifiée car le besoin Moules par technologies est remonté par un autre canal (cf commentaire Fabrice du 01Jun16)
    """
    if row.ProcessType == "C3M":
        TechnoMoule = "C3M / Prime EB"
        if row.zone == "ADN":
            TechnoMoule = TechnoMoule + " - AdN"
        else:
            TechnoMoule = TechnoMoule + " - Europe"
    elif row.DesignType == "OFFTAKE":
        TechnoMoule = "EB / PA / TR / EB Lite"
    else:
        input_mold_techno = str(row.MoldTechno)
        if input_mold_techno.count("EB")+input_mold_techno.count("PA")+input_mold_techno.count("TR")>0:
            TechnoMoule = "EB / PA / TR / EB Lite"
        else:
            TechnoMoule = "EI"
    return TechnoMoule

def load_gantt_calculator_params():
    gc_params = p.read_excel(
        os.path.join(os.path.dirname(__file__), "gantt_calculator_params_v1.xlsx"),
        sheet_name="params",
        keep_default_na=False,
        na_values=[""], engine="openpyxl"
    )  # keep_default_na prevent pandas from reading NA(North America) as NaN (Not a Number)
    return gc_params


def calculate_milestones_dates(
    gc_params,
    lc_date,
    category,
    dev_zone,
    out_of_zonelaunch,
    project_type,
    garniture_type,
    nb_molds_per_loop_balise,
    nb_molds_per_loop_market,
    nb_molds_decli,
    nb_indus_pdt,
    AVG_INDUS_CAPACITY_PER_WEEK_AND_PER_PLANT=1,
):
    """
        nb_molds_per_loop_market = NbMouleTdG
        
    """
    project_phases = ["B0 - B1", "B1 - B2", "B2 - B3", "G0 - G1", "G1 - G2", "G2 - LC"]

    # =SI(OU($G$16=$W$42;$G$16=$W$44);14/365+1;1)
    Vacation_or_shutdown_adjustment = (
        14 / 365 + 1 if category in ["All season / summer / SUV", "Commercial"] else 1
    )

    if project_type == "B+M":
        switch_for_project_type = 1
    elif project_type.count("Pre-BB") > 0:
        switch_for_project_type = 2
    else:
        switch_for_project_type = 0
    # ### Gantt params preparation
    # Fixed Params
    gc_params.loc[:, "type_param"] = gc_params.type_param.fillna(method="ffill")

    # Calculated params
    ### ZONEs params
    # 7 weeks =
    # +2 for materials
    #   1 - Fab Z
    #   1 - Logistic
    # +4 weeks / EL
    #   1 - Prep between P2 and EL
    #   1 - Prep EL and tires released
    #   1  - Mount mold
    #   1 - Logistics for 32 P
    # +1 week for SI
    gc_params.loc[
        (gc_params.type_param == "Zone") & (gc_params.value_param == "Asia"), "G1 - G2"
    ] = (14 if project_type == "Market (2-loops)" else 7)
    # + 1 week / loop for weather impact on adherence testing
    gc_params.loc[
        (gc_params.type_param == "Zone") & (gc_params.value_param == "Europe"),
        "G1 - G2",
    ] = (2 if project_type == "Market (2-loops)" else 1)
    ### garnaiture_type params
    # =7++SI(G19=W23;7;0)
    gc_params.loc[
        (gc_params.type_param == "garniture_type")
        & (gc_params.value_param == "C3M / Prime EB - AdN"),
        "G1 - G2",
    ] = (14 if project_type == "Market (2-loops)" else 7)
    # =5+SI(G19=W23;5;0)
    gc_params.loc[
        (gc_params.type_param == "garniture_type")
        & (gc_params.value_param == "C3M / Prime EB - Europe"),
        "G1 - G2",
    ] = (10 if project_type == "Market (2-loops)" else 5)
    # =5+SI(G19=W23;5;0)
    gc_params.loc[
        (gc_params.type_param == "garniture_type")
        & (gc_params.value_param == "C3M / Prime EI - AdN"),
        "G1 - G2",
    ] = (10 if project_type == "Market (2-loops)" else 5)
    # =3+SI(G19=W23;3;0)
    gc_params.loc[
        (gc_params.type_param == "garniture_type")
        & (gc_params.value_param == "C3M / Prime EI - Europe"),
        "G1 - G2",
    ] = (6 if project_type == "Market (2-loops)" else 3)
    # =2+SI(G19=W23;2;0)
    gc_params.loc[
        (gc_params.type_param == "garniture_type")
        & (gc_params.value_param == "EB / PA / TR / EB Lite"),
        "G1 - G2",
    ] = (4 if project_type == "Market (2-loops)" else 2)
    ### garnaiture_type indus_type_pre_G2
    # =4+SI(G19=W23;4;0)
    gc_params.loc[
        (gc_params.type_param == "indus_type_pre_G2")
        & (gc_params.value_param == "C - Coex"),
        "G1 - G2",
    ] = (8 if project_type == "Market (2-loops)" else 4)
    ### category params
    ## WALID : DEV NON TERMINEE ICI
    # "Cloute / Studded tire"  ou "Winter"
    # =(SI(G19=W23; 24;12)-AB15)*AB16*365/(12*7)
    param1 = 24 if project_type == "Market (2-loops)" else 12
    # (param1-AB15)*AB16*365/(12*7)
    gc_params.loc[
        (gc_params.type_param == "category")
        & (gc_params.value_param.isin(["Winter", "Cloute / Studded tire"])),
        "G1 - G2",
    ] = "NOT FINISHED"

    ### Timing impact in weeks
    timing_impacts = p.DataFrame(columns=project_phases)
    # Impact of : development_zone
    dev_zone_impact = gc_params.loc[
        (gc_params.type_param == "Zone") & (gc_params.value_param == dev_zone),
        project_phases,
    ]
    timing_impacts.loc["development_zone", :] = dev_zone_impact.values[0]
    if project_type != "B+M":  # =SI(G19=W18;RECHERCHEV(G17;W38:AC41;5);0)
        timing_impacts.loc["development_zone", "G0 - G1"] = 0
    # Impact of : out_of_zone_launch
    # =SI(G19=W34;10;SI(G18=W74;6;0))
    if project_type == "Off-Take":
        impact_out_of_zone_launch = 10
    elif out_of_zonelaunch:
        impact_out_of_zone_launch = 6
    else:
        impact_out_of_zone_launch = 0
    timing_impacts.loc["out_of_zone_launch", "G2 - LC"] = impact_out_of_zone_launch
    timing_impacts
    # Impact of : project_type
    impact = gc_params.loc[
        (gc_params.type_param == "project_type_duration_by_phase")
        & (gc_params.value_param == project_type),
        project_phases,
    ]
    timing_impacts.loc["project_type", :] = impact.values[0]
    # Impact of : garnaiture_type
    impact = gc_params.loc[
        (gc_params.type_param == "garniture_type")
        & (gc_params.value_param == garniture_type),
        project_phases,
    ]
    timing_impacts.loc["garniture_type", :] = impact.values[0]
    ## Il y a une erreur dans le ganttCalculator : il prend dans la cellule O20 ou on va chercher les infos G1-G2 ald G2-LC
    ## La ligne ci-dessous est pour s'aligner au GantCalcultor avec son erreur pour pouvoir comparer. une fois la validation du nouvelle Algo est faite on peut supprimer la ligne ci-dessous
    timing_impacts.loc["garniture_type", "G2 - LC"] = timing_impacts.loc[
        "garniture_type", "G1 - G2"
    ]
    # Impact of : indus_type
    impact = gc_params.loc[
        (gc_params.type_param == "indus_type_pre_G2"), project_phases
    ]
    timing_impacts.loc["indus_type", :] = impact.values[0]
    # Impact of : buffer
    # =SI(G19=W24;0;2)
    impact = 0 if project_type == "Off-Take" else 2
    timing_impacts.loc["buffer", "B1 - B2"] = impact
    timing_impacts.loc["buffer", "G1 - G2"] = impact
    # =SI(G19=W24;3/12*365/7;0)
    timing_impacts.loc["buffer", "G2 - LC"] = (
        3 / 12 * 365 / 7 if project_type == "Off-Take" else 0
    )
    if project_type == "B+M":
        # Impact of : balise_molds
        # Walid : Je choisi de prendre le meme nombre de moules dans les deux boucles entre B1-B2
        # Walid : J'impose qu'un balise = 2 boucles (à faire évoluer plus tard si besoin)
        BALISE_NB_LOOPS = 2
        # =SI(G29<4;0;ARRONDI.SUP(G29/2;0)*2-4)
        impact = (
            0
            if nb_molds_per_loop_balise < 4
            else arrondi_sup(nb_molds_per_loop_balise / 2.0) * 2 - 4
        )
        timing_impacts.loc["balise_molds", "B1 - B2"] = BALISE_NB_LOOPS * impact
        # Impact of nb_KM_technos :
        timing_impacts.loc["nb_KM_technos", "B1 - B2"] = 1
    # Impact of : market_molds
    # LOOP_1
    # =SI(G19=W31;0;SI(G37<6;0;ARRONDI.SUP(G37/2;0)*2-6))
    if project_type == "Maintenance":
        impact = 0
    elif nb_molds_per_loop_market < 6:
        impact = 0
    else:
        impact = arrondi_sup(nb_molds_per_loop_market / 2) * 2 - 6
    timing_impacts.loc["market_molds_loop_1", "G1 - G2"] = impact
    # LOOP_2
    # =SI(G19=W33;SI(G39<6;0;ARRONDI.SUP(G39/2;0)*2-6);0)
    if project_type == "Market (2-loops)":
        if nb_molds_per_loop_market < 6:
            impact = 0
        else:
            impact = arrondi_sup(nb_molds_per_loop_market / 2) * 2 - 6
    else:
        impact = 0
    timing_impacts.loc["market_molds_loop_2", "G1 - G2"] = impact
    # Impact of : g2_lc_indus_type
    # =SI(G19=W21;-5;RECHERCHEV(G41;W69:AC70;7))
    timing_impacts.loc["proto_then_pre_serie", "G2 - LC"] = (
        -5 if project_type == "Maintenance" else 0
    )
    # Impact of : nb_molds_decli
    # =SI(G19=W24;(G42-1)/8*4.3;(G42-1)/G43+SI(G20=W62;1;2))
    param1 = 1 if garniture_type == "EI" else 2
    impact = (
        (nb_molds_decli - 1) / 8 * 4.3
        if project_type == "Off-Take"
        else (nb_molds_decli - 1) / CPV_MOLD_CAPACITY_PER_WEEK + param1
    )
    timing_impacts.loc["molds_decli", "G2 - LC"] = impact
    # Impact of : nb_inuds_pdt
    # =(G44-1)/(G45*G46)+SI(G20=W62;1;2)
    param1 = 1 if garniture_type == "EI" else 2
    if AVG_INDUS_CAPACITY_PER_WEEK_AND_PER_PLANT <= 0:
        AVG_INDUS_CAPACITY_PER_WEEK_AND_PER_PLANT = 1
        print(
            "AVG_INDUS_CAPACITY_PER_WEEK_AND_PER_PLANT could not be equal to zero. it was reset to 1."
        )
    impact = (nb_indus_pdt - 1) / (
        NB_PLANTS * AVG_INDUS_CAPACITY_PER_WEEK_AND_PER_PLANT
    ) + param1
    timing_impacts.loc["indus_pdt", "G2 - LC"] = impact
    timing_impacts

    gc_params

    multiplier_relating_to_project_type = gc_params.loc[
        (gc_params.type_param == "use_or_suppress_subtotal")
        & (gc_params.value_param == project_type),
        project_phases,
    ]
    multiplier_relating_to_project_type

    # =SOMME(J17:J48)*7/365*12*X16
    Stage_duration_without_tire_type_adjustment = (
        timing_impacts.sum() * 7 / 365 * 12 * multiplier_relating_to_project_type
    )

    # =SI(G19=W24;SOMME(N28;N19);SOMME(N17:N46))*7/365*12*AB16
    if project_type == "Off-Take":
        param1 = (
            timing_impacts.loc["buffer", "G1 - G2"]
            + timing_impacts.loc["project_type", "G1 - G2"]
        )
    else:
        param1 = timing_impacts.sum()["G1 - G2"]
    Stage_duration_without_tire_type_adjustment.loc[:, "G1 - G2"] = (
        param1 * 7 / 365 * 12 * multiplier_relating_to_project_type["G1 - G2"]
    )

    # =SI(G19=W24;SOMME(O28;O19;O42;O18);(SOMME(O17:O41)+GRANDE.VALEUR(O42:O46;1)))*7/365*12*AC16
    if project_type == "Off-Take":
        param1 = (
            timing_impacts.loc["buffer", "G2 - LC"]
            + timing_impacts.loc["project_type", "G2 - LC"]
            + timing_impacts.loc["out_of_zone_launch", "G2 - LC"]
            + timing_impacts.loc["molds_decli", "G2 - LC"]
        )
    else:
        # We can have the same results with a different formula : sum(a1+a2+...+aN-2)+max(aN-1, aN) replaced by sum(a1+...aN)-min(aN-1, aN)
        param1 = timing_impacts.sum()["G2 - LC"] - min(
            timing_impacts.loc["molds_decli", "G2 - LC"],
            timing_impacts.loc["indus_pdt", "G2 - LC"],
        )
    Stage_duration_without_tire_type_adjustment.loc[:, "G2 - LC"] = (
        param1 * 7 / 365 * 12 * multiplier_relating_to_project_type["G2 - LC"]
    )
    Stage_duration_without_tire_type_adjustment

    # Category : Calculated params
    # "B0 - B1" =(10-X15)*X16*365/(12*7)
    def calcul_category_param_for_balise(leadtime, phase):
        res = (
            (leadtime - Stage_duration_without_tire_type_adjustment[phase])
            * multiplier_relating_to_project_type[phase]
            * 365
            / (12 * 7)
        )
        return res.values[0]

    winter_indexes = (gc_params.value_param == "Winter") | (
        gc_params.value_param == "Cloute / Studded tire"
    )
    # "B0 - B1" =(10-X15)*X16*365/(12*7)
    gc_params.loc[
        (gc_params.type_param == "category") & (winter_indexes), "B0 - B1"
    ] = calcul_category_param_for_balise(10, "B0 - B1")
    gc_params.loc[
        (gc_params.type_param == "category") & (winter_indexes), "B1 - B2"
    ] = calcul_category_param_for_balise(24, "B1 - B2")
    gc_params.loc[
        (gc_params.type_param == "category") & (winter_indexes), "B2 - B3"
    ] = calcul_category_param_for_balise(11, "B2 - B3")
    # G0-G1 : =(2.9-AA15)*AA16*365/(12*7)
    gc_params.loc[
        (gc_params.type_param == "category") & (winter_indexes), "G0 - G1"
    ] = calcul_category_param_for_balise(2.9, "G0 - G1")
    # G1-G2 : =(SI(G19=W23; 24;12)-AB15)*AB16*365/(12*7)
    param = 24 if project_type == "Market (2-loops)" else 12
    gc_params.loc[
        (gc_params.type_param == "category") & (winter_indexes), "G1 - G2"
    ] = calcul_category_param_for_balise(param, "G1 - G2")
    # G2-G3 : =(SI(G17=W38;15;12)-AC15)*AC16*365/(12*7)
    param = 15 if dev_zone == "Asia" else 12
    gc_params.loc[
        (gc_params.type_param == "category") & (winter_indexes), "G2 - LC"
    ] = calcul_category_param_for_balise(param, "G2 - LC")
    gc_params.loc[(gc_params.type_param == "category")]

    # Category : time impact
    # =RECHERCHEV(G16;W42:AC45;2)
    timing_impacts.loc["category", :] = gc_params.loc[
        (gc_params.type_param == "category") & (gc_params.value_param == category),
        project_phases,
    ].values[0]

    # Stage duration  - with tire type and vacaton adjustment
    # Stage_duration_with_adjustment = p.Series(index=project_phases)
    # =(X15+J16*12*7/365)*X12 for : "B0 - B1", "B1 - B2", "B2 - B3"
    # balise_phases = ["B0 - B1", "B1 - B2", "B2 - B3"]
    Stage_duration_with_adjustment = (
        Stage_duration_without_tire_type_adjustment
        + timing_impacts.loc["category", :] * 12 * 7 / 365
    ) * Vacation_or_shutdown_adjustment
    # Market phase : =SI(G19=W24;AA15;(AA15+M16*12*7/365)*AA12)
    market_phases = ["G0 - G1", "G1 - G2", "G2 - LC"]
    sd = Stage_duration_without_tire_type_adjustment[market_phases]
    ti_cat = timing_impacts.loc["category", market_phases]
    if project_type == "Off-Take":
        res = sd
    else:
        res = (sd + ti_cat * 12 * 7 / 365) * Vacation_or_shutdown_adjustment
    Stage_duration_with_adjustment.loc[:, market_phases] = res.values[0]

    # =SI(X13=2;"n/a";AC14*AC16)
    gap_Milestones = (
        Stage_duration_with_adjustment * multiplier_relating_to_project_type
    )

    #from datetime import timedelta

    # gaps are expressed in month
    G2_date = lc_date - p.Timedelta(days=gap_Milestones["G2 - LC"].values[0] * 365 / 12)
    G1_date = G2_date - p.Timedelta(days=gap_Milestones["G1 - G2"].values[0] * 365 / 12)
    G0_date = G1_date - p.Timedelta(days=gap_Milestones["G0 - G1"].values[0] * 365 / 12)

    # Balise
    # B2 : =SI(X13=0;"n/a";SI(X13=2;G15-H6*365/12;F9+SI(OU(SI(G16=W43;VRAI;FAUX);SI(G16=W45;VRAI;FAUX);;);89;28)))
    # We will implement only B+M / Market cases :
    # F9+SI(OU(SI(G16=W43;VRAI;FAUX);SI(G16=W45;VRAI;FAUX);;);89;28)
    # F9 + 89 si winter/cloute sinon 28
    B2_date = (
        G0_date + p.Timedelta(days=89)
        if category in ["Winter", "Cloute / Studded tire"]
        else G0_date + p.Timedelta(days=89)
    )
    # B3 : =SI(X13=0;"n/a";G5+H6*365/12)
    B3_date = B2_date + p.Timedelta(days=gap_Milestones["B2 - B3"].values[0]) * 365 / 12
    B1_date = B2_date - p.Timedelta(days=gap_Milestones["B1 - B2"].values[0]) * 365 / 12
    B0_date = B1_date - p.Timedelta(days=gap_Milestones["B0 - B1"].values[0]) * 365 / 12
    return (
        B0_date,
        B1_date,
        B2_date,
        B3_date,
        G0_date,
        G1_date,
        G2_date,
        lc_date,
    )  # , timing_impacts




def get_one_decli_duration(is_full_regulatory_test=True, is_labelling_mandatory=False):
    one_decli_duration = 47 # in weeks
    if is_full_regulatory_test:
        one_decli_duration = one_decli_duration + 10
        #streamlit.write("Regulatory tests take 16 weeks (to take into account DOT or CCC)")
    #else:
    #    streamlit.write("Regulatory tests take 6 weeks (no DOT or CCC are included)")
    if is_labelling_mandatory:
        #streamlit.write("We switch from 3 months (RAG only) to 4 months (RAG and Labelling constraint)")
        one_decli_duration = one_decli_duration + 4
    return one_decli_duration


def get_milestones_dates(gc_params, current_project, ignore_fixed_milestones=False):
    ## Call the Gantt Calculator
    try:
        lc_date = convert_excel_date(current_project.CommercialLaunchDate)
    except:
        lc_date = current_project.CommercialLaunchDate
        # print("warning : verify commercial launch date format")
    category = set_Categorie(current_project)
    project_type = set_TypeGantt(current_project)
    garniture_type = set_TechnoMoule(current_project)
    out_of_zonelaunch = "Yes" if current_project.LaunchScope == "WW" else "No"
    nb_molds_per_loop_balise = 4
    Mold_entries_per_week_in_G2LC = current_project.Mold_entries_per_week_in_G2LC
    # DOC : Dans l'ancien sizingtool : nb_molds_per_loop_market = current_project.TdGMold
    # La colonne TdGMold n'etant plus remplie on va calculer le nombre de TdGMold en sommant le nombre de briques TdG
    nb_molds_per_loop_market = (
        current_project.TdGMain_Loop1
        + current_project.TdGMain_Loop2
        + current_project.TdGSec_Loop1
        + current_project.TdGSec_Loop2
    )
    nb_molds_decli = current_project.MoulistStudies
    # DOC : dans l'ancien ST : nb_indus_pdt = current_project.Declis
    # Dans le nouveau ST on considère qu'on a autant d'indus que : nbMoldDecli + MultisourcedCai
    nb_indus_pdt = current_project.MoulistStudies + current_project.MultiSourcedCai
    dev_zone = set_Design_Zone_for_gantt_calculator(current_project.zone)
    print((lc_date,
        category,
        dev_zone,
        out_of_zonelaunch,
        project_type,
        garniture_type,
        nb_molds_per_loop_balise,
        nb_molds_per_loop_market,
        nb_molds_decli,
        nb_indus_pdt,
        Mold_entries_per_week_in_G2LC))

    (
        B0_date,
        B1_date,
        B2_date,
        B3_date,
        G0_date,
        G1_date,
        G2_date,
        lc_date,
    ) = calculate_milestones_dates(
        gc_params,
        lc_date,
        category,
        dev_zone,
        out_of_zonelaunch,
        project_type,
        garniture_type,
        nb_molds_per_loop_balise,
        nb_molds_per_loop_market,
        nb_molds_decli,
        nb_indus_pdt,
        Mold_entries_per_week_in_G2LC)


    # If a milestone is already described in the product plan then it will override the calculated value
    if not ignore_fixed_milestones:
        for fixed_milestone in (
            current_project.loc[
                current_project.index.isin(["B0", "B1", "B2", "B3", "G0", "G1", "G2"])
            ]
            .dropna()
            .index.tolist()
        ):
            if fixed_milestone == "G0":
                G0_date = current_project["G0"]
            elif fixed_milestone == "G1":
                G1_date = current_project["G1"]
            elif fixed_milestone == "G2":
                G2_date = current_project["G2"]
            elif fixed_milestone == "B0":
                B0_date = current_project["B0"]
            elif fixed_milestone == "B1":
                B1_date = current_project["B1"]
            elif fixed_milestone == "B2":
                B2_date = current_project["B2"]
            elif fixed_milestone == "B3":
                B3_date = current_project["B3"]

    return [B0_date, B1_date, B2_date, B3_date, G0_date, G1_date, G2_date, lc_date]


def get_new_milestones_dates(gc_params, test_project, status=False, is_full_regulatory_test=True, is_labelling_mandatory=False, verbose=False):
    # We calculate diferently the G2-LC duration

    if not status:
        status = streamlit.empty()

    B0, B1, B2, B3, G0, G1, G2, LC = get_milestones_dates(gc_params, test_project)
    one_decli_duration = get_one_decli_duration(is_full_regulatory_test=is_full_regulatory_test, is_labelling_mandatory=is_labelling_mandatory)
    if verbose:
        streamlit.write("The total duration of One declination is %d weeks" % one_decli_duration)

    G1G2_duration = G2-G1
    G0G1_duration = G1-G0
    B2B3_duration = B3-B2
    B1B2_duration = B2-B1
    B0B1_duration = B1-B0

    # New delay added to G1-G2 to take into account time needed for RI 
    # Les RI sont absentes des Gantt Standard et font en réaliter perdre jusqu'à deux mois sur les jalons avant G2. (entre 1000 et 3000 pneus).
    # La RI permet de démontrer la faisabilité industrielle et passer l'ATG3 ce qui permet de passer le G2
    G1G2_RI_delay = p.Timedelta(days=int(6 * 7))

    # New duration of a decli: take into account regulatory tests
    total_decli_duration = (test_project.Declis/test_project.Mold_entries_per_week_in_G2LC)-1+one_decli_duration  # expressed in weeks
    total_decli_duration_in_months = total_decli_duration / 4.345238095
    if verbose:
        streamlit.write("Total declination duration is %.1f months" % total_decli_duration_in_months)

    ATG2_G2_duration = p.Timedelta(days=int(2.5 * 30)) 
    new_ATG_2 = LC - p.Timedelta(days=int(total_decli_duration * 7))
    new_G2 = new_ATG_2 + ATG2_G2_duration
    if verbose:
        streamlit.write(f"Declination phase starts just after ATG2 ({new_ATG_2})")
        streamlit.write(f"G2 milestone is 2,5 months after ATG2 ==> ({new_G2})")

    is_winter_or_AS = str(test_project.GanttCategory).count("WINTER") + str(test_project.GanttCategory).count("A/S")
    if is_winter_or_AS and new_ATG_2.month!=4:
        previous_ATG_2 = new_ATG_2
        if new_ATG_2.month>=4:
            new_ATG_2 = p.Timestamp(datetime.date(year=new_ATG_2.year, month=4, day=1)) #p.to_datetime(f'01/05/{new_G1.year}', format='%d/%m/%Y') # datetime.datetime(year=new_G1.year, month=5, day=1, hour=0, minute=0) #
        else:
            new_ATG_2 = p.Timestamp(datetime.date(year=new_ATG_2.year-1, month=4, day=1))
        previous_G2 = new_G2
        new_G2 = new_ATG_2 + ATG2_G2_duration
        #streamlit.markdown(f"**ATG2 should be in April for Winter and A/S:**")
        #streamlit.markdown(f"> ATG2 was shifted from {str(previous_ATG_2)} to {str(new_ATG_2)}. And G2 is shifter from {previous_G2} to {new_G2}")

    new_G1 = new_G2 - G1G2_duration - G1G2_RI_delay
    if verbose:
        streamlit.write(f"We add 6 weeks to the G1-G2 phase to take into account the RI. new G1 = {new_G1}")
    if is_winter_or_AS and (new_G1.month>=7):
        new_G1_july = p.Timestamp(datetime.date(year=new_G1.year, month=7, day=1)) #p.to_datetime(f'01/05/{new_G1.year}', format='%d/%m/%Y') # datetime.datetime(year=new_G1.year, month=5, day=1, hour=0, minute=0) #
        if verbose:
            status.warning(f"G1 can not be after July for Winter and A/S. G1 was shifted from {str(new_G1)} to {str(new_G1_july)}")
        new_G1 = new_G1_july

    if hasattr(test_project, 'Declis_pourcents'):
        pourcent_declis = test_project.Declis_pourcents
    else:
        pourcent_declis = 100.

    if is_winter_or_AS and pourcent_declis<100:
        # Adjust the ratio of CAIs available
        original_nb_decli = test_project.Declis * 100 / pourcent_declis
        if verbose:
            streamlit.write("original number of Decli = %.1f" %  original_nb_decli)
        atg2_lc_duration = LC - new_ATG_2
        atg2_lc_duration_weeks = atg2_lc_duration.days/7.
        if verbose:
                status.write("New ATG2 = "+str(new_ATG_2))
                status.write("atg2_lc_duration_months = %.1f" %  (atg2_lc_duration_weeks / 4.345238095))
        nb_achievable_decli = (atg2_lc_duration_weeks+1-one_decli_duration)*test_project.Mold_entries_per_week_in_G2LC
        ratio_achievable_declis = min(100, nb_achievable_decli / original_nb_decli* 100)
        if verbose and abs(ratio_achievable_declis - pourcent_declis) > 1: # if gap more than 1% show the message below
            streamlit.success("The new gantt allow to achieve %.1f %% Declinations (original ratio is %.1f %%)" % (ratio_achievable_declis, pourcent_declis))
    new_G0 = new_G1 - G0G1_duration
    new_B2 = new_G1
    new_B1 = new_B2 - B1B2_duration
    new_B0 = new_B1 - B0B1_duration
    new_B3 = new_B2 + B2B3_duration

    return new_B0, new_B1, new_B2, new_B3, new_G0, new_G1, new_G2, LC



"""if __name__ == "__main__":
    # INPUTS :
    lc_date = p.to_datetime("01/05/2021", format="%d/%m/%Y")  # G15
    category = "Winter"  # G16
    dev_zone = "Europe"  # G17
    out_of_zonelaunch = True  # G18
    project_type = "B+M"  # G19
    garniture_type = "C3M / Prime EB - Europe"  # G20
    nb_molds_per_loop_balise = 4  # G29 et G33
    nb_molds_per_loop_market = (
        10  # G37 et G39 : Le sizingTool rempli cette valeur avec le NbMouleTdG
    )
    nb_molds_decli = 10  # G42
    nb_indus_pdt = 10  # G44
    (
        B0_date,
        B1_date,
        B2_date,
        B3_date,
        G0_date,
        G1_date,
        G2_date,
    ) = calculate_milestones_dates(
        lc_date,
        category,
        dev_zone,
        out_of_zonelaunch,
        project_type,
        garniture_type,
        nb_molds_per_loop_balise,
        nb_molds_per_loop_market,
        nb_molds_decli,
        nb_indus_pdt,
    )
"""
