#!/usr/bin/env python3
"""
Extract REDCap-mapped fields from clinical notes using Ollama.

Outputs notes_redcap.jsonl where each record contains:
  - patient_id, document_reference_id, note_date, title
  - redcap_fields: dict of REDCap variable name → extracted value
    - radio/dropdown fields: string code ("1", "2", ...) or null
    - checkbox fields: list of string codes (["1", "3"]) or []
    - text/integer fields: extracted string or null
"""
import ast
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Field schema: all fields the LLM will attempt to extract.
# Each entry: variable_name → {label, type, choices (for categorical)}
# type: "radio" | "dropdown" | "checkbox" | "text" | "integer" | "yesno"
# choices: dict of code → label (only for categorical types)
# ---------------------------------------------------------------------------
REDCAP_FIELDS = {
    # ---- Medical History ---------------------------------------------------
    "hand_dom": {
        "label": "Hand dominance",
        "type": "dropdown",
        "choices": {"1": "Left", "2": "Right", "3": "Ambidextrous"},
    },
    "sz_age": {
        "label": "Age at seizure onset (years)",
        "type": "integer",
    },
    "medhx_etio": {
        "label": "Suspected seizure type / event classification",
        "type": "radio",
        "choices": {
            "0": "Generalized epilepsy",
            "1": "Focal or multifocal epilepsy",
            "2": "Both focal and generalized",
            "3": "Psychogenic non-epileptic events (PNEE) / FND",
            "4": "Physiological non-epileptic events (syncope, sleep disorder, etc.)",
            "5": "Combined / multiple (e.g., FND and focal epilepsy)",
            "999": "Unknown",
        },
    },
    "medhx_etio_focal": {
        "label": "Etiology of focal seizures (select all that apply)",
        "type": "checkbox",
        "choices": {
            "1": "Mesial temporal sclerosis (MTS / hippocampal sclerosis)",
            "2": "Prior traumatic brain injury (TBI)",
            "3": "Post-stroke or vascular injury",
            "4": "Post-infectious",
            "5": "Tumor (neoplasm)",
            "6": "Vascular lesion (cavernoma, AVM)",
            "7": "Cortical dysplasia or migrational abnormality",
            "8": "Autoimmune or inflammatory",
            "9": "Genetic",
            "999": "Unknown",
        },
    },
    "medhx_szsyndrome": {
        "label": "Confirmed epilepsy syndrome?",
        "type": "dropdown",
        "choices": {"1": "Yes", "2": "No", "999": "Unknown"},
    },
    "medhx_szsyndrome_type": {
        "label": "Epilepsy syndrome type",
        "type": "dropdown",
        "choices": {
            "1": "MTLE-HS (mesial temporal lobe epilepsy with hippocampal sclerosis)",
            "2": "Lennox-Gastaut syndrome (LGS)",
            "3": "CDKL5-DEE",
            "4": "Childhood absence epilepsy (CAE)",
            "5": "Childhood occipital visual epilepsy (COVE)",
            "6": "DEE-SWAS",
            "7": "Dravet syndrome",
            "8": "EIDEE",
            "9": "EIMFS",
            "10": "Epilepsy with auditory features (EAF)",
            "11": "Epilepsy with eyelid myoclonia (EEM)",
            "12": "Juvenile myoclonic epilepsy (JME)",
            "999": "Other",
        },
    },
    "medhx_prior_episgy": {
        "label": "Prior epilepsy surgery (including neuromodulation)?",
        "type": "dropdown",
        "choices": {"1": "Yes", "2": "No", "3": "Unknown"},
    },
    "medhx_priorepisgy_type": {
        "label": "Prior epilepsy surgery types (select all that apply)",
        "type": "checkbox",
        "choices": {
            "1": "Lesionectomy",
            "2": "Anterior temporal lobectomy (ATL)",
            "3": "Selective amygdalohippocampectomy (SAH)",
            "4": "Neocortical resection",
            "5": "Multi-lobar resection",
            "6": "Hemispherotomy or hemispherectomy",
            "7": "Open corpus callosotomy",
            "8": "Laser corpus callosotomy",
            "9": "Laser ablation (LITT)",
            "10": "Radiofrequency ablation (RFA)",
            "11": "Multiple subpial transections",
            "12": "Vagus nerve stimulator (VNS)",
            "13": "Deep brain stimulator (DBS)",
            "14": "Responsive neurostimulator (RNS)",
            "999": "Other",
        },
    },
    "medhx_neurohx": {
        "label": "Neurological comorbidities (select all that apply)",
        "type": "checkbox",
        "choices": {
            "1": "Ischemic stroke",
            "2": "Intracranial hemorrhage",
            "3": "Traumatic brain injury (TBI)",
            "4": "Dementia or mild cognitive impairment (MCI)",
            "5": "Headaches or migraine",
            "6": "Parkinson's disease",
            "7": "Tremor or other movement disorder",
            "0": "None",
            "999": "Unknown",
        },
    },
    "medhx_psych": {
        "label": "Psychiatric comorbidities (select all that apply)",
        "type": "checkbox",
        "choices": {
            "1": "Depression",
            "2": "Anxiety",
            "3": "Bipolar disorder",
            "4": "PTSD",
            "5": "Schizophrenia or other psychotic disorder",
            "6": "Alcohol or substance use disorder",
            "0": "None",
            "999": "Unknown",
        },
    },
    "medhx_si": {
        "label": "Known history of suicidal ideation or suicide attempt?",
        "type": "yesno",
        "choices": {"1": "Yes", "0": "No"},
    },
    "medhx_driving": {
        "label": "Currently driving?",
        "type": "dropdown",
        "choices": {"1": "Yes", "2": "No", "3": "Unclear or unknown"},
    },
    "medhx_sgy_cand_yn": {
        "label": "Is this patient a surgical candidate?",
        "type": "radio",
        "choices": {"1": "Yes", "2": "No", "3": "Unclear"},
    },
    # ---- Seizure Characteristics -------------------------------------------
    "emu_sz_type": {
        "label": "Most frequent seizure type / semiology",
        "type": "dropdown",
        "choices": {
            "1": "Primary generalized tonic-clonic",
            "2": "Focal motor with retained awareness",
            "3": "Focal non-motor with retained awareness (sensory, autonomic, aura)",
            "4": "Focal motor with impaired awareness",
            "5": "Focal non-motor with impaired awareness",
            "6": "Events with retained awareness, NOS",
            "7": "Staring spells or behavioral arrest, NOS",
            "8": "Hypermotor, NOS",
            "9": "Myoclonus or brief jerks",
            "10": "Convulsions NOS",
            "99": "Other",
        },
    },
    "emu_sz_type1_freq": {
        "label": "Frequency of primary seizure type",
        "type": "dropdown",
        "choices": {
            "1": "Multiple times per day",
            "2": "Daily",
            "3": "Multiple times per week",
            "4": "Weekly",
            "5": "Multiple times per month",
            "6": "Monthly",
            "7": "Multiple times per year",
            "8": "Yearly or less frequent",
            "9": "Random clusters",
        },
    },
    # ---- ASMs on Admission -------------------------------------------------
    "emu_asm_number": {
        "label": "Number of anti-seizure medications (ASMs) on admission (not counting rescue meds)",
        "type": "dropdown",
        "choices": {
            "0": "None",
            "1": "One",
            "2": "Two",
            "3": "Three",
            "4": "Four",
            "5": "Five or more",
        },
    },
    "emu_asm_type": {
        "label": "ASMs taken on admission (select all that apply)",
        "type": "checkbox",
        "choices": {
            "1": "levetiracetam (Keppra)",
            "2": "lamotrigine (Lamictal)",
            "3": "carbamazepine (Tegretol)",
            "4": "oxcarbazepine (Trileptal)",
            "5": "eslicarbazepine (Aptiom)",
            "6": "brivaracetam (Briviact)",
            "7": "topiramate (Topamax)",
            "8": "zonisamide (Zonegran)",
            "9": "clobazam (Onfi)",
            "10": "clonazepam (Klonopin)",
            "11": "diazepam (Valium)",
            "12": "lorazepam (Ativan)",
            "13": "valproic acid / divalproex (Depakote)",
            "14": "gabapentin (Neurontin)",
            "15": "lacosamide (Vimpat)",
            "16": "pregabalin (Lyrica)",
            "17": "phenytoin / fosphenytoin (Dilantin)",
            "18": "phenobarbital",
            "19": "cannabidiol (Epidiolex)",
            "20": "cenobamate (Xcopri)",
            "21": "ethosuximide (Zarontin)",
            "22": "rufinamide (Banzel)",
            "23": "felbamate (Felbatol)",
            "24": "perampanel (Fycompa)",
            "25": "acetazolamide (Diamox)",
            "26": "primidone (Mysoline)",
            "27": "stiripentol (Diacomit)",
            "28": "vigabatrin (Sabril)",
            "29": "fenfluramine (Fintepla)",
            "99": "Other ASM not listed",
        },
    },
    "emu_asm_sfx": {
        "label": "ASM side effects on admission",
        "type": "dropdown",
        "choices": {
            "1": "Yes - dose limiting side effects",
            "2": "Yes - side effects present but not dose limiting",
            "3": "No side effects",
            "99": "Unclear",
        },
    },
    # ---- ASMs on Discharge -------------------------------------------------
    "emu_asmdc_number": {
        "label": "Number of ASMs on discharge",
        "type": "dropdown",
        "choices": {
            "0": "None",
            "1": "One",
            "2": "Two",
            "3": "Three",
            "4": "Four",
            "5": "Five or more",
        },
    },
    "emu_asmdc_type": {
        "label": "ASMs taken on discharge (select all that apply)",
        "type": "checkbox",
        "choices": {
            "1": "levetiracetam (Keppra)",
            "2": "lamotrigine (Lamictal)",
            "3": "carbamazepine (Tegretol)",
            "4": "oxcarbazepine (Trileptal)",
            "5": "eslicarbazepine (Aptiom)",
            "6": "brivaracetam (Briviact)",
            "7": "topiramate (Topamax)",
            "8": "zonisamide (Zonegran)",
            "9": "clobazam (Onfi)",
            "10": "clonazepam (Klonopin)",
            "11": "diazepam (Valium)",
            "12": "lorazepam (Ativan)",
            "13": "valproic acid / divalproex (Depakote)",
            "14": "gabapentin (Neurontin)",
            "15": "lacosamide (Vimpat)",
            "16": "pregabalin (Lyrica)",
            "17": "phenytoin / fosphenytoin (Dilantin)",
            "18": "phenobarbital",
            "19": "cannabidiol (Epidiolex)",
            "20": "cenobamate (Xcopri)",
            "21": "ethosuximide (Zarontin)",
            "22": "rufinamide (Banzel)",
            "23": "felbamate (Felbatol)",
            "24": "perampanel (Fycompa)",
            "25": "acetazolamide (Diamox)",
            "26": "primidone (Mysoline)",
            "27": "stiripentol (Diacomit)",
            "28": "vigabatrin (Sabril)",
            "29": "fenfluramine (Fintepla)",
            "99": "Other ASM not listed",
        },
    },
    # ---- EMU Discharge Summary ---------------------------------------------
    "emu_dcevents_type": {
        "label": "Discharge diagnosis from EMU admission",
        "type": "radio",
        "choices": {
            "1": "Epilepsy",
            "2": "FND (functional neurological disorder / PNEE)",
            "3": "Mixed FND and epilepsy",
            "4": "Physiologic non-epileptic events (syncope, parasomnias, etc.)",
            "5": "Inconclusive study",
            "6": "Other",
        },
    },
    "emu_epilepsytype": {
        "label": "Epilepsy type / localization",
        "type": "dropdown",
        "choices": {
            "1": "Focal - single focus",
            "2": "Focal - two foci",
            "3": "Multifocal (3 or more foci)",
            "4": "Generalized - idiopathic",
            "5": "Generalized - symptomatic",
            "6": "Unlocalizable",
        },
    },
    "emu_epilepsy_intract": {
        "label": "Is the epilepsy medically refractory (drug-resistant)?",
        "type": "dropdown",
        "choices": {"1": "Yes", "2": "No", "3": "Unclear"},
    },
    "emu_sxcandidate": {
        "label": "Surgical candidacy status",
        "type": "radio",
        "choices": {
            "1": "Yes, surgical candidate and surgery was discussed",
            "2": "Yes, surgical candidate but patient not amenable",
            "3": "Yes, surgical candidate but surgery not yet discussed",
            "4": "Not currently a candidate but possible in future",
            "5": "No, not a surgical candidate",
            "999": "Unknown",
        },
    },
    # ---- MRI ---------------------------------------------------------------
    "mri_yn": {
        "label": "MRI performed or ordered?",
        "type": "radio",
        "choices": {"1": "Yes, performed", "2": "No but ordered/scheduled", "0": "No"},
    },
    "mri_normal_abnormal": {
        "label": "MRI result",
        "type": "radio",
        "choices": {"1": "Normal", "2": "Abnormal"},
    },
    "mri_lateralization": {
        "label": "MRI abnormality lateralization",
        "type": "radio",
        "choices": {
            "1": "Left",
            "2": "Right",
            "3": "Bilateral",
            "4": "Midline",
            "5": "Multifocal",
        },
    },
    "mri_l_localization": {
        "label": "MRI localization (left hemisphere)",
        "type": "radio",
        "choices": {
            "1": "Temporal",
            "2": "Frontal",
            "3": "Parietal",
            "4": "Occipital",
            "5": "Sub-cortical",
            "6": "Other",
        },
    },
    "mri_r_localization": {
        "label": "MRI localization (right hemisphere)",
        "type": "radio",
        "choices": {
            "1": "Temporal",
            "2": "Frontal",
            "3": "Parietal",
            "4": "Occipital",
            "5": "Sub-cortical",
            "6": "Other",
        },
    },
    "mri_lesion_left": {
        "label": "MRI lesion type (left)",
        "type": "dropdown",
        "choices": {
            "1": "Hippocampal sclerosis / mesial temporal atrophy",
            "2": "Cavernoma or vascular lesion",
            "3": "Neoplasm (DNET, glioma, or other tumor)",
            "4": "Focal cortical dysplasia (FCD)",
            "5": "Stroke or encephalomalacia (including TBI sequelae)",
            "6": "Polymicrogyria",
            "7": "Heterotopia",
            "8": "Cortical tubers (TSC)",
            "99": "Other",
        },
    },
    "mri_lesion_right": {
        "label": "MRI lesion type (right)",
        "type": "dropdown",
        "choices": {
            "1": "Hippocampal sclerosis / mesial temporal atrophy",
            "2": "Cavernoma or vascular lesion",
            "3": "Neoplasm (DNET, glioma, or other tumor)",
            "4": "Focal cortical dysplasia (FCD)",
            "5": "Stroke or encephalomalacia (including TBI sequelae)",
            "6": "Polymicrogyria",
            "7": "Heterotopia",
            "8": "Cortical tubers (TSC)",
            "99": "Other",
        },
    },
    # ---- Other Imaging -----------------------------------------------------
    "pet_yn": {
        "label": "FDG-PET performed or ordered?",
        "type": "radio",
        "choices": {"1": "Yes, performed", "2": "No but ordered/scheduled", "0": "No"},
    },
    "fmri_yn": {
        "label": "fMRI (functional MRI) performed or ordered?",
        "type": "radio",
        "choices": {"1": "Yes, performed", "2": "No but ordered/scheduled", "0": "No"},
    },
    "wada_yn": {
        "label": "WADA test performed or ordered?",
        "type": "radio",
        "choices": {"1": "Yes, performed", "2": "No but ordered/scheduled", "0": "No"},
    },
}

# Fields where the model should return a list of codes (checkbox / multi-select)
CHECKBOX_FIELDS = {k for k, v in REDCAP_FIELDS.items() if v["type"] == "checkbox"}

# Fields grouped by clinical domain for focused sub-prompts
GROUP_FIELDS: Dict[str, List[str]] = {
    "medical_history": [
        "hand_dom", "sz_age", "medhx_etio", "medhx_etio_focal",
        "medhx_szsyndrome", "medhx_szsyndrome_type", "medhx_prior_episgy",
        "medhx_priorepisgy_type", "medhx_neurohx", "medhx_psych",
        "medhx_si", "medhx_driving", "medhx_sgy_cand_yn",
    ],
    "seizure": ["emu_sz_type", "emu_sz_type1_freq"],
    "asms": ["emu_asm_number", "emu_asm_type", "emu_asm_sfx", "emu_asmdc_number", "emu_asmdc_type"],
    "discharge": ["emu_dcevents_type", "emu_epilepsytype", "emu_epilepsy_intract", "emu_sxcandidate"],
    "imaging": [
        "mri_yn", "mri_normal_abnormal", "mri_lateralization",
        "mri_l_localization", "mri_r_localization",
        "mri_lesion_left", "mri_lesion_right",
        "pet_yn", "fmri_yn", "wada_yn",
    ],
}

# Targeted instructions injected per group to address known model failure patterns
GROUP_INSTRUCTIONS: Dict[str, str] = {
    "medical_history": (
        "IMPORTANT: sz_age is the patient's AGE AT FIRST SEIZURE ONSET, "
        "NOT their current age. Look for phrases like 'seizures began at age X', "
        "'first seizure at age X', 'epilepsy onset at age X', 'since age X', "
        "'onset at X years old', 'initial seizure at X'. Do not use the patient's current age.\n"
        "IMPORTANT for medhx_neurohx: Only check a neurological comorbidity if it is explicitly "
        "listed as a separate current neurological diagnosis. Do NOT check 'ischemic stroke' (code 1) "
        "simply because the patient has post-stroke epilepsy — the stroke is the seizure etiology, "
        "not a separate current comorbidity. Do NOT check 'headaches/migraine' (code 5) unless "
        "migraine is explicitly listed as a separate diagnosis. If no neurological comorbidities "
        "are listed beyond epilepsy itself, select code 0 (None).\n"
        "IMPORTANT for medhx_etio: "
        "Code 0 = Generalized epilepsy (e.g., JME, absence epilepsy, generalized tonic-clonic). "
        "Code 1 = Focal epilepsy (e.g., temporal lobe epilepsy, frontal lobe epilepsy, MTS, post-stroke focal). "
        "Code 2 = Both focal AND generalized features present. "
        "Code 3 = PNEE/FND only (psychogenic non-epileptic events, functional neurological disorder — no epilepsy). "
        "Code 4 = Physiological non-epileptic events (syncope, parasomnias). "
        "Code 5 = Mixed FND + epilepsy (patient has both PNEE and confirmed epileptic seizures). "
        "Autoimmune epilepsy is focal (code 1). Dravet syndrome is generalized (code 0)."
    ),
    "seizure": (
        "IMPORTANT: emu_sz_type refers to the MOST FREQUENT seizure type at the time of "
        "EMU admission. If multiple types are described, choose the one reported as most frequent. "
        "Do not default to code 1 (primary generalized tonic-clonic) unless the note explicitly "
        "states the seizures are generalized.\n"
        "IMPORTANT for emu_sz_type1_freq — use these exact mappings: "
        "1=multiple per day (several times daily, 2-3x/day), "
        "2=daily (once a day, every day), "
        "3=multiple per week (2-3x/week, several times weekly), "
        "4=weekly (once a week, every week), "
        "5=multiple per month (2-3x/month, several times monthly), "
        "6=monthly (once a month, every month), "
        "7=multiple per year (every few months, 3-4x/year), "
        "8=yearly or less frequent (once a year, rare). "
        "If the patient has FND/PNEE only with no epileptic seizures, return null for this field."
    ),
    "asms": (
        "IMPORTANT: Count only regularly SCHEDULED anti-seizure medications. "
        "Do NOT count rescue or PRN medications (e.g., diazepam rectal, lorazepam PRN, "
        "intranasal midazolam) in emu_asm_number or emu_asm_type. "
        "Apply the same rule for discharge ASMs (emu_asmdc_number, emu_asmdc_type).\n"
        "IMPORTANT for emu_asmdc_number and emu_asmdc_type: These refer to medications at DISCHARGE, "
        "not admission. Look for a discharge medications section, phrases like 'discharged on', "
        "'discharge medications include', 'at time of discharge', or 'sent home on'. "
        "The discharge list may differ from admission — do not copy the admission list. "
        "If the patient was discharged on zero ASMs, return '0' for emu_asmdc_number."
    ),
    "discharge": (
        "IMPORTANT for emu_sxcandidate: code 4 = not currently a surgical candidate but "
        "may become one in the future (e.g., more workup needed). "
        "Code 5 = definitively not a candidate at this time. "
        "Only use code 5 if the note explicitly states surgery is not indicated."
    ),
    "imaging": (
        "IMPORTANT: For pet_yn, fmri_yn, and wada_yn — return code 0 (No) if the test is "
        "NOT mentioned anywhere in the note. Only return code 1 (Yes, performed) if the note "
        "explicitly states the test was completed. Only return code 2 (No but ordered) if the "
        "note explicitly states it was ordered or scheduled. Do not infer or assume."
    ),
}


def build_prompt(note: Dict, group: str) -> str:
    text = note.get("note_text_clean") or note.get("note_text", "")
    field_names = GROUP_FIELDS[group]

    # Build a plain-text field reference list (no JSON comments)
    field_lines: List[str] = []
    json_keys: List[str] = []
    for var in field_names:
        meta = REDCAP_FIELDS[var]
        ftype = meta["type"]
        label = meta["label"]
        choices = meta.get("choices", {})
        json_keys.append(f'  "{var}": null')

        if ftype == "checkbox":
            options = ", ".join(f'{k}={v}' for k, v in choices.items())
            field_lines.append(f'- {var} [MULTI]: {label}. Codes: {options}')
        elif ftype in ("radio", "dropdown", "yesno"):
            options = ", ".join(f'{k}={v}' for k, v in choices.items())
            field_lines.append(f'- {var} [SINGLE]: {label}. Codes: {options}')
        elif ftype == "integer":
            field_lines.append(f'- {var} [INTEGER]: {label}')
        else:
            field_lines.append(f'- {var} [TEXT]: {label}')

    fields_reference = "\n".join(field_lines)
    json_template = "{\n" + ",\n".join(json_keys) + "\n}"
    extra_instruction = GROUP_INSTRUCTIONS.get(group, "")
    special_section = f"\nSPECIAL INSTRUCTIONS:\n{extra_instruction}\n" if extra_instruction else ""

    return f"""You are a clinical data abstractor for an epilepsy surgery research database.
Extract structured data from the clinical note below to populate REDCap fields.

RULES:
- Return STRICT valid JSON only — no markdown fences, no comments, no explanation.
- [SINGLE] fields: return the numeric code as a string e.g. "1", or null if not in the note.
- [MULTI] fields: return an array of code strings e.g. ["1","3"], or [] if not in the note.
- [INTEGER] fields: return the number as a string e.g. "12", or null if not in the note.
- Do not guess. Only extract what is explicitly stated in the note.
- Replace every null below with the extracted value. Keep all field names exactly as shown.
{special_section}
FIELD REFERENCE:
{fields_reference}

Return this JSON with null replaced by extracted values:
{json_template}

Clinical note:
{text}
""".strip()


def call_ollama(base_url: str, model: str, prompt: str) -> str:
    resp = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=240,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def extract_group(note: Dict, group: str, base_url: str, model: str) -> Dict:
    """Run one focused Ollama call for a single field group. Returns {field: raw_value}."""
    prompt = build_prompt(note, group)
    raw_response = call_ollama(base_url, model, prompt)
    parsed = parse_response(raw_response)

    field_names = GROUP_FIELDS[group]
    if parsed is None:
        print(f"  [warn] parse failure for group '{group}' on {note.get('document_reference_id', '?')}")
        return {var: ([] if REDCAP_FIELDS[var]["type"] == "checkbox" else None) for var in field_names}

    # Only return fields belonging to this group — ignore any extras the model emitted
    return {var: parsed.get(var) for var in field_names}


def parse_response(raw: str) -> Optional[Dict]:
    """Extract JSON from model response, tolerating markdown wrapping."""
    raw = raw.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    import re
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        raw = fence_match.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fall back to extracting the outermost { ... } block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _try_parse(value):
    """Parse a string that may be a Python literal (e.g. "['a', 'b']" or "{'code': '1'}")."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        pass
    return value


def _label_to_code(val_str: str, choices: Dict[str, str]) -> Optional[str]:
    """
    Try to map a text value to a REDCap code using the field's choices dict.
    Returns the code string if matched, else None.
    """
    if not val_str or not choices:
        return None

    # Already a valid code
    if val_str in choices:
        return val_str

    # Boolean strings — match against Yes/No labels
    lower = val_str.lower()
    if lower in ("true", "yes"):
        for code, label in choices.items():
            if label.lower().startswith("yes"):
                return code
    if lower in ("false", "no"):
        for code, label in choices.items():
            if label.lower().startswith("no"):
                return code

    # Exact case-insensitive label match
    for code, label in choices.items():
        if label.lower() == lower:
            return code

    # Value is contained within a label (e.g. "Abnormal" in "Abnormal finding")
    for code, label in choices.items():
        if lower == label.lower().split()[0]:  # first word match
            return code

    return None


def _normalize_single(value, meta: Dict) -> Optional[str]:
    """Normalize a model output value to a valid REDCap code string for a single-value field."""
    choices = meta.get("choices", {})

    if value is None or value == "":
        return None

    # If value is a complex type (list, dict) or a stringified one, try to unwrap it
    parsed = _try_parse(value)

    # Unwrap list → take first element
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else None

    # Unwrap dict → prefer 'code' key, else first value
    if isinstance(parsed, dict):
        parsed = parsed.get("code") or next(iter(parsed.values()), None)

    if parsed is None:
        return None

    val_str = str(parsed).strip()

    if not choices:
        # text/integer field — return as-is
        return val_str

    return _label_to_code(val_str, choices)


def _normalize_checkbox_item(value, choices: Dict[str, str]) -> Optional[str]:
    """Normalize one item in a checkbox list to a code, or None if unrecognizable."""
    if value is None:
        return None
    parsed = _try_parse(value)
    if isinstance(parsed, dict):
        parsed = parsed.get("code") or next(iter(parsed.values()), None)
    if parsed is None:
        return None
    val_str = str(parsed).strip()
    return _label_to_code(val_str, choices)


# Fields where null model output should fall back to a clinically safe default.
# Justified: EMU discharge summaries always document these if performed/ordered.
# Absence of mention = "No".
FIELD_DEFAULTS: Dict[str, str] = {
    "pet_yn": "0",      # FDG-PET: not mentioned → No
    "fmri_yn": "0",     # fMRI: not mentioned → No
    "wada_yn": "0",     # WADA: not mentioned → No
    "emu_asm_sfx": "3", # ASM side effects: not mentioned → No side effects
}


def normalize_fields(raw_fields: Dict) -> Dict:
    """Normalize model output: map text labels to codes, unwrap complex objects."""
    out = {}
    for var, meta in REDCAP_FIELDS.items():
        value = raw_fields.get(var)
        ftype = meta["type"]
        choices = meta.get("choices", {})

        if ftype == "checkbox":
            # Model should return a list of codes; may return labels or complex objects
            if isinstance(value, list):
                items = value
            elif value is None or value == "":
                items = []
            else:
                # Possibly a stringified list or single value
                parsed = _try_parse(value)
                items = parsed if isinstance(parsed, list) else [parsed]

            normalized = []
            for item in items:
                code = _normalize_checkbox_item(item, choices)
                if code and code not in normalized:
                    normalized.append(code)

            # If nothing was checked and the field has a "None" sentinel (code "0"),
            # select it explicitly — covers medhx_neurohx___0 and medhx_psych___0
            if not normalized and "0" in choices:
                normalized = ["0"]

            out[var] = normalized

        elif ftype in ("radio", "dropdown", "yesno"):
            out[var] = _normalize_single(value, meta)

        else:
            # text / integer — pass through as string
            if value is None or value == "":
                out[var] = None
            else:
                out[var] = str(value).strip()

    # Apply clinically justified defaults for fields where null = "No/None"
    for var, default_code in FIELD_DEFAULTS.items():
        if out.get(var) is None or out.get(var) == "":
            out[var] = default_code

    return out


def main():
    load_dotenv()

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    clean_path = Path(os.getenv("CLEAN_NOTES_JSONL", "./data/processed/notes_clean.jsonl"))
    raw_path = Path(os.getenv("RAW_NOTES_JSONL", "./data/raw/notes_raw.jsonl"))
    out_path = Path(os.getenv("REDCAP_JSONL", "./data/processed/notes_redcap.jsonl"))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not clean_path.exists() and not raw_path.exists():
        raise FileNotFoundError(f"No input file found at {clean_path} or {raw_path}")
    in_path = clean_path if clean_path.exists() else raw_path

    count = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            note = json.loads(line)
            print(f"  Processing: {note.get('title', 'untitled')}")

            # Run one focused Ollama call per field group and merge results
            merged_raw: Dict = {}
            for group in GROUP_FIELDS:
                group_result = extract_group(note, group, base_url, model)
                merged_raw.update(group_result)
                print(f"    [{group}] done")

            redcap_fields = normalize_fields(merged_raw)

            row = {
                "patient_id": note.get("patient_id", ""),
                "document_reference_id": note.get("document_reference_id", ""),
                "note_date": note.get("note_date", ""),
                "title": note.get("title", ""),
                "redcap_fields": redcap_fields,
            }
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1

    print(f"\nWrote {count} records to {out_path}")


if __name__ == "__main__":
    main()
