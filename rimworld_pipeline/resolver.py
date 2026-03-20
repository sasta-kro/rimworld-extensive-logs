from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

from rimworld_pipeline.snapshots import SaveSnapshot


THING_ID_PATTERN = re.compile(r"^(?P<thing_type>[A-Za-z_]+)(?P<numeric_id>\d+)$")


@dataclass(frozen=True)
class FactionInfo:
    faction_id: str
    faction_name: str | None
    faction_def: str | None


@dataclass(frozen=True)
class EntityInfo:
    entity_id: str
    raw_id: str
    display_label: str
    kind_def: str | None
    thing_def: str | None
    faction_id: str | None
    faction_name: str | None
    role_hint: str | None
    origin_scope: str
    is_dead: bool


@dataclass(frozen=True)
class ResolvedEntityRef:
    raw_id: str | None
    entity_id: str | None
    display_label: str | None
    kind_def: str | None
    thing_def: str | None
    faction_id: str | None
    faction_name: str | None
    role_hint: str | None


def normalize_entity_id(raw_id: str | None) -> str | None:
    if raw_id is None:
        return None

    normalized_id = raw_id.strip()
    if not normalized_id or normalized_id == "null":
        return None

    if normalized_id.startswith(("Thing_", "Faction_", "Ideo_", "Map_", "WorldObject_")):
        return normalized_id

    if THING_ID_PATTERN.match(normalized_id):
        return f"Thing_{normalized_id}"

    return normalized_id


def label_from_raw_id(raw_id: str | None) -> str | None:
    normalized_id = normalize_entity_id(raw_id)
    if normalized_id is None:
        return None

    if normalized_id.startswith("Thing_"):
        thing_body = normalized_id.removeprefix("Thing_")
        match = THING_ID_PATTERN.match(thing_body)
        if match is not None:
            return match.group("thing_type").replace("_", " ")
        return thing_body.replace("_", " ")

    return normalized_id.replace("_", " ")


def clean_text(xml_element: ET.Element | None) -> str | None:
    if xml_element is None or xml_element.text is None:
        return None

    normalized_text = xml_element.text.strip()
    return normalized_text if normalized_text else None


def build_name_from_name_triple(name_element: ET.Element | None) -> str | None:
    if name_element is None:
        return None

    nick_name = clean_text(name_element.find("nick"))
    first_name = clean_text(name_element.find("first"))
    last_name = clean_text(name_element.find("last"))

    if nick_name:
        return nick_name
    if first_name and last_name:
        return f"{first_name} {last_name}"
    return first_name or last_name


def clean_optional_text(raw_text: str | None) -> str | None:
    if raw_text is None:
        return None
    normalized_text = raw_text.strip()
    return normalized_text if normalized_text and normalized_text != "null" else None


def infer_role_hint(
    thing_def: str | None,
    kind_def: str | None,
    faction_info: FactionInfo | None,
    guest_element: ET.Element | None,
    is_dead: bool,
) -> str | None:
    join_status = clean_text(guest_element.find("joinStatus")) if guest_element is not None else None
    host_faction = clean_text(guest_element.find("hostFaction")) if guest_element is not None else None
    slave_faction = clean_text(guest_element.find("slaveFaction")) if guest_element is not None else None

    if faction_info and faction_info.faction_def:
        lowered_faction_def = faction_info.faction_def.lower()
        if lowered_faction_def == "playercolony":
            return "colonist"
        if "pirate" in lowered_faction_def or "rough" in lowered_faction_def or "savage" in lowered_faction_def:
            return "raider"
        if lowered_faction_def in {"outlandercivil", "tribecivil", "ancients"}:
            return "guest"

    if slave_faction and slave_faction != "null":
        return "prisoner"
    if join_status == "JoinAsColonist":
        return "colonist"
    if host_faction and host_faction != "null":
        return "guest"

    if kind_def:
        lowered_kind = kind_def.lower()
        if "prisoner" in lowered_kind or "slave" in lowered_kind:
            return "prisoner"
        if "colonist" in lowered_kind:
            return "colonist"
        if "town_" in lowered_kind or "villager" in lowered_kind or "councilman" in lowered_kind:
            return "guest"
        if "drifter" in lowered_kind or "space refugee" in lowered_kind or "refugee" in lowered_kind:
            return "guest"

    if thing_def and thing_def.lower() != "human":
        if faction_info is None:
            return "wild_animal"
        return "animal"

    if is_dead:
        return "dead_pawn"

    return None


def merge_entity_info(existing: EntityInfo | None, candidate: EntityInfo) -> EntityInfo:
    if existing is None:
        return candidate

    display_label = existing.display_label
    if existing.display_label == existing.raw_id and candidate.display_label != candidate.raw_id:
        display_label = candidate.display_label

    return EntityInfo(
        entity_id=existing.entity_id,
        raw_id=existing.raw_id,
        display_label=display_label,
        kind_def=existing.kind_def or candidate.kind_def,
        thing_def=existing.thing_def or candidate.thing_def,
        faction_id=existing.faction_id or candidate.faction_id,
        faction_name=existing.faction_name or candidate.faction_name,
        role_hint=existing.role_hint or candidate.role_hint,
        origin_scope=existing.origin_scope,
        is_dead=existing.is_dead or candidate.is_dead,
    )


class EntityResolver:
    def __init__(self) -> None:
        self._factions_by_id: dict[str, FactionInfo] = {}
        self._entities_by_id: dict[str, EntityInfo] = {}

    @classmethod
    def from_snapshot(cls, save_snapshot: SaveSnapshot) -> EntityResolver:
        resolver = cls()
        resolver._load_factions(save_snapshot.world_root)
        resolver._load_world_pawns(save_snapshot.world_root)
        resolver._load_map_pawns(save_snapshot)
        resolver._load_tale_pawn_data(save_snapshot.world_root)
        return resolver

    def resolve_reference(self, raw_id: str | None) -> ResolvedEntityRef:
        normalized_id = normalize_entity_id(raw_id)
        if normalized_id is None:
            return ResolvedEntityRef(
                raw_id=raw_id,
                entity_id=None,
                display_label=None,
                kind_def=None,
                thing_def=None,
                faction_id=None,
                faction_name=None,
                role_hint=None,
            )

        entity_info = self._entities_by_id.get(normalized_id)
        if entity_info is not None:
            return ResolvedEntityRef(
                raw_id=raw_id,
                entity_id=entity_info.entity_id,
                display_label=entity_info.display_label,
                kind_def=entity_info.kind_def,
                thing_def=entity_info.thing_def,
                faction_id=entity_info.faction_id,
                faction_name=entity_info.faction_name,
                role_hint=entity_info.role_hint,
            )

        return ResolvedEntityRef(
            raw_id=raw_id,
            entity_id=normalized_id,
            display_label=label_from_raw_id(normalized_id) or normalized_id,
            kind_def=None,
            thing_def=None,
            faction_id=None,
            faction_name=None,
            role_hint=None,
        )

    def _load_factions(self, world_root: ET.Element) -> None:
        for faction_element in world_root.findall("./game/world/factionManager/allFactions/li"):
            faction_load_id = clean_text(faction_element.find("loadID"))
            if faction_load_id is None:
                continue

            faction_id = f"Faction_{faction_load_id}"
            self._factions_by_id[faction_id] = FactionInfo(
                faction_id=faction_id,
                faction_name=clean_optional_text(faction_element.findtext("name")),
                faction_def=clean_optional_text(faction_element.findtext("def")),
            )

    def _load_world_pawns(self, world_root: ET.Element) -> None:
        pawn_sections = {
            "./game/world/worldPawns/pawnsAlive/li": ("world", False),
            "./game/world/worldPawns/pawnsMothballed/li": ("world", False),
            "./game/world/worldPawns/pawnsDead/li": ("world", True),
        }

        for pawn_path, (origin_scope, is_dead) in pawn_sections.items():
            for pawn_element in world_root.findall(pawn_path):
                self._add_entity_from_pawn_element(
                    pawn_element=pawn_element,
                    origin_scope=origin_scope,
                    is_dead=is_dead,
                )

    def _load_map_pawns(self, save_snapshot: SaveSnapshot) -> None:
        map_pawn_paths = [
            "./mapPawns/AllPawnsSpawned/li",
            "./mapPawns/AllPawnsUnspawned/li",
            "./mapPawns/FreeColonistsSpawned/li",
            "./mapPawns/PrisonersOfColonySpawned/li",
        ]

        for map_snapshot in save_snapshot.map_snapshots:
            for map_pawn_path in map_pawn_paths:
                for pawn_element in map_snapshot.root.findall(map_pawn_path):
                    self._add_entity_from_pawn_element(
                        pawn_element=pawn_element,
                        origin_scope=f"map:{map_snapshot.map_id}",
                        is_dead=False,
                    )

    def _load_tale_pawn_data(self, world_root: ET.Element) -> None:
        for candidate_element in world_root.iter():
            if candidate_element.find("pawn") is None:
                continue
            if candidate_element.find("name") is None:
                continue

            raw_id = clean_text(candidate_element.find("pawn"))
            normalized_id = normalize_entity_id(raw_id)
            if normalized_id is None:
                continue

            faction_id = normalize_entity_id(clean_text(candidate_element.find("faction")))
            faction_info = self._factions_by_id.get(faction_id) if faction_id else None

            display_label = (
                build_name_from_name_triple(candidate_element.find("name"))
                or label_from_raw_id(normalized_id)
                or normalized_id
            )
            kind_def = clean_text(candidate_element.find("kind"))

            self._add_entity_info(
                EntityInfo(
                    entity_id=normalized_id,
                    raw_id=raw_id or normalized_id,
                    display_label=display_label,
                    kind_def=kind_def,
                    thing_def="Human" if normalized_id.startswith("Thing_Human") else None,
                    faction_id=faction_id,
                    faction_name=faction_info.faction_name if faction_info else None,
                    role_hint=infer_role_hint(
                        thing_def="Human" if normalized_id.startswith("Thing_Human") else None,
                        kind_def=kind_def,
                        faction_info=faction_info,
                        guest_element=None,
                        is_dead=False,
                    ),
                    origin_scope="tale",
                    is_dead=False,
                )
            )

    def _add_entity_from_pawn_element(
        self,
        pawn_element: ET.Element,
        origin_scope: str,
        is_dead: bool,
    ) -> None:
        raw_id = clean_text(pawn_element.find("id"))
        normalized_id = normalize_entity_id(raw_id)
        if normalized_id is None:
            return

        faction_id = normalize_entity_id(clean_text(pawn_element.find("faction")))
        faction_info = self._factions_by_id.get(faction_id) if faction_id else None
        thing_def = clean_text(pawn_element.find("def"))
        kind_def = clean_text(pawn_element.find("kindDef"))

        display_label = (
            build_name_from_name_triple(pawn_element.find("name"))
            or label_from_raw_id(normalized_id)
            or normalized_id
        )

        self._add_entity_info(
            EntityInfo(
                entity_id=normalized_id,
                raw_id=raw_id or normalized_id,
                display_label=display_label,
                kind_def=kind_def,
                thing_def=thing_def,
                faction_id=faction_id,
                faction_name=faction_info.faction_name if faction_info else None,
                role_hint=infer_role_hint(
                    thing_def=thing_def,
                    kind_def=kind_def,
                    faction_info=faction_info,
                    guest_element=pawn_element.find("guest"),
                    is_dead=is_dead,
                ),
                origin_scope=origin_scope,
                is_dead=is_dead,
            )
        )

    def _add_entity_info(self, candidate: EntityInfo) -> None:
        existing = self._entities_by_id.get(candidate.entity_id)
        self._entities_by_id[candidate.entity_id] = merge_entity_info(existing, candidate)
