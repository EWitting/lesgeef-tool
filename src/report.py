import numpy as np
from .models import Planning, DatumPrikker, Lesgever, Les
from .config import RoosterConfig


def generate_report(planning: Planning, datumprikker: DatumPrikker, config: RoosterConfig = None) -> str:
    """Genereert een rapport over het rooster, en de datumprikker.
    
    Noemt: 
    - Status van datumprikker (hoeveel lesgevers al ingevuld (en min. 1 keer beschikbaar), hoeveel nog te vullen)
    - Status van gevulde lessen, op basis van minimum volgens config
    - Lessen die nog niet zijn ingevuld
    - Lesgevers die het vaakst zijn ingedeeld.
    - Lessen waar iemand met misschien is ingedeeld.
    - Lessen waar iemand meerdere lessen per week geeft."""

    if config is None:
        config = RoosterConfig()

    # --- Datumprikker Status ---
    al_ingevuld = len(datumprikker.lesgevers_al_ingevuld)
    nog_te_vullen = len(datumprikker.lesgevers_nog_te_vullen)
    beschikbaar_ingevuld = (np.array(datumprikker.beschikbaarheid) != 'Nee').any(axis=1).sum()

    # --- Rooster Status ---
    ingevulde_lessen = [les for les in datumprikker.lessen if les.lesgevers and len(les.lesgevers) > 0]
    niet_ingevulde_lessen = [les for les in datumprikker.lessen if not les.lesgevers or len(les.lesgevers) == 0]
    
    # Lessen met te weinig lesgevers
    lessen_tekort = [les for les in ingevulde_lessen if len(les.lesgevers) < config.lesgever_minimum]
    
    # Lessen met ervaren lesgevers
    lessen_zonder_ervaring = [les for les in ingevulde_lessen 
                              if not any(lg.ervaring_jaren >= 1 for lg in les.lesgevers)]
    
    # --- Lesgevers Statistieken ---
    lesgever_stats = _bereken_lesgever_stats(datumprikker)
    
    # --- Misschien Indelingen ---
    misschien_lessen = _vind_misschien_lessen(datumprikker)
    
    # --- Meerdere Lessen per Week ---
    week_conflicten = _vind_week_conflicten(datumprikker)
    
    # --- Rapport Samenstellen ---
    rapport_onderdelen = []
    
    # Datumprikker sectie
    rapport_onderdelen.append("=== DATUMPRIKKER STATUS ===")
    rapport_onderdelen.append(f"📝 Ingevuld: {al_ingevuld} lesgevers")
    rapport_onderdelen.append(f"⏳ Nog te vullen: {nog_te_vullen} lesgevers") 
    rapport_onderdelen.append(f"✅ Beschikbaar (≥1x): {beschikbaar_ingevuld} lesgevers")
    rapport_onderdelen.append("")
    
    # Rooster sectie
    rapport_onderdelen.append("=== ROOSTER STATUS ===")
    rapport_onderdelen.append(f"📚 Totaal lessen: {len(datumprikker.lessen)}")
    rapport_onderdelen.append(f"✅ Ingevuld: {len(ingevulde_lessen)} lessen")
    rapport_onderdelen.append(f"❌ Niet ingevuld: {len(niet_ingevulde_lessen)} lessen")
    
    if lessen_tekort:
        rapport_onderdelen.append(f"⚠️  Te weinig lesgevers (<{config.lesgever_minimum}): {len(lessen_tekort)} lessen")
    
    if lessen_zonder_ervaring:
        rapport_onderdelen.append(f"🔰 Geen ervaren lesgever: {len(lessen_zonder_ervaring)} lessen")
    
    rapport_onderdelen.append("")
    
    # Niet ingevulde lessen details
    if niet_ingevulde_lessen:
        rapport_onderdelen.append("=== NIET INGEVULDE LESSEN ===")
        for les in niet_ingevulde_lessen:
            rapport_onderdelen.append(f"📅 {les.datum.strftime('%a %d %b')} {les.tijd}")
        rapport_onderdelen.append("")
    
    # Incomplete lessen
    if lessen_tekort:
        rapport_onderdelen.append("=== LESSEN MET TE WEINIG LESGEVERS ===")
        for les in lessen_tekort:
            rapport_onderdelen.append(
                f"📅 {les.datum.strftime('%a %d %b')} {les.tijd} ({len(les.lesgevers)}/{config.lesgever_minimum})"
            )
        rapport_onderdelen.append("")
        
    # Misschien indelingen
    if misschien_lessen:
        rapport_onderdelen.append("=== MISSCHIEN INDELINGEN ===")
        for les, lesgevers in misschien_lessen:
            lgv_namen = [lg.naam for lg in lesgevers]
            rapport_onderdelen.append(f"{les.datum.strftime('%a %d %b')} {les.tijd}: {', '.join(lgv_namen)}")
        rapport_onderdelen.append("")

    # Lesgever statistieken
    if lesgever_stats:
        rapport_onderdelen.append("=== LESGEVER VERDELING ===")
        sorted_stats = sorted(lesgever_stats.items(), key=lambda x: x[1], reverse=True)
        for lesgever_naam, aantal in sorted_stats:  # Top 10
            rapport_onderdelen.append(f"{lesgever_naam}: {aantal} lessen")
        rapport_onderdelen.append("")

    
    # Week conflicten
    if week_conflicten:
        rapport_onderdelen.append("=== MEERDERE LESSEN PER WEEK ===")
        for week, conflicts in week_conflicten.items():
            rapport_onderdelen.append(f"📅 Week {week}:")
            for lesgever, lessen in conflicts.items():
                les_info = [f"{les.datum.strftime('%a %d/%m')} {les.tijd}" for les in lessen]
                rapport_onderdelen.append(f"   👨‍🏫 {lesgever}: {', '.join(les_info)}")
        rapport_onderdelen.append("")

    # Mensen om reminders naar te sturen
    rapport_onderdelen.append("=== MENSEN OM REMINDERS NAAR TE STUREN ===")
    for lesgever in datumprikker.lesgevers_nog_te_vullen:
        rapport_onderdelen.append(f"{lesgever.naam}")
    rapport_onderdelen.append("")
    
    return "\n".join(rapport_onderdelen)



def _bereken_lesgever_stats(datumprikker: DatumPrikker) -> dict[str, int]:
    """Berekent hoeveel lessen elke lesgever heeft gekregen."""
    stats = {}
    is_beschikbaar = (np.array(datumprikker.beschikbaarheid) != 'Nee').any(axis=1)
    for lesgever_index in np.where(is_beschikbaar)[0]:
        stats[datumprikker.lesgevers_al_ingevuld[lesgever_index].naam] = 0
    for les in datumprikker.lessen:
        for lesgever in les.lesgevers:
            stats[lesgever.naam] = stats.get(lesgever.naam, 0) + 1
    return stats


def _vind_misschien_lessen(datumprikker: DatumPrikker) -> list[tuple[Les, list[Lesgever]]]:
    """Vindt alle lessen waar iemand met 'Misschien' is ingedeeld."""
    misschien_lessen = []
    
    for les in datumprikker.lessen:
        if not les.lesgevers:
            continue
            
        misschien_lesgevers = []
        for lesgever in les.lesgevers:
            beschikbaarheid = vind_beschikaarheid(datumprikker, lesgever, les)
            if beschikbaarheid == "Misschien":
                misschien_lesgevers.append(lesgever)
        
        if misschien_lesgevers:
            misschien_lessen.append((les, misschien_lesgevers))
    
    return misschien_lessen


def _vind_week_conflicten(datumprikker: DatumPrikker) -> dict[str, dict[str, list[Les]]]:
    """Vindt lesgevers die meerdere lessen in dezelfde week hebben."""
    week_conflicten = {}
    
    # Groepeer lessen per week en lesgever
    lesgever_weeks = {}
    for les in datumprikker.lessen:
        if not les.lesgevers:
            continue
            
        week_key = f"{les.datum.year}-W{les.datum.isocalendar()[1]:02d}"
        
        for lesgever in les.lesgevers:
            if lesgever.naam not in lesgever_weeks:
                lesgever_weeks[lesgever.naam] = {}
            if week_key not in lesgever_weeks[lesgever.naam]:
                lesgever_weeks[lesgever.naam][week_key] = []
            lesgever_weeks[lesgever.naam][week_key].append(les)
    
    # Vind conflicten (meer dan 1 les per week)
    for lesgever_naam, weeks in lesgever_weeks.items():
        for week_key, lessen in weeks.items():
            if len(lessen) > 1:
                if week_key not in week_conflicten:
                    week_conflicten[week_key] = {}
                week_conflicten[week_key][lesgever_naam] = lessen
    
    return week_conflicten


def vind_beschikaarheid(datumprikker: DatumPrikker, lesgever: Lesgever, les: Les) -> str | None:
    """Vindt de beschikbaarheid van een lesgever voor een les."""
    if lesgever not in datumprikker.lesgevers_al_ingevuld or les not in datumprikker.lessen:
        return None

    lesgever_index = datumprikker.lesgevers_al_ingevuld.index(lesgever)
    les_index = datumprikker.lessen.index(les)
    return datumprikker.beschikbaarheid[lesgever_index][les_index]

