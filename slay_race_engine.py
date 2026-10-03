import copy
import random


class Card:

    def __init__(
        self,
        card_id: str,
        name: str,
        cost: int,
        effects: list,
        description: str,
        level: int = 1,
        base_id: str = None,
    ):
        self.instance_id = f"{card_id}_{random.randint(1000, 9999)}"
        self.card_id = card_id
        self.base_id = base_id or card_id
        self.name = name
        self.cost = cost
        self.effects = effects
        self.description = description
        self.level = level

    def to_dict(self):
        return {
            "instance_id": self.instance_id,
            "card_id": self.card_id,
            "base_id": self.base_id,
            "name": self.name,
            "cost": self.cost,
            "effects": self.effects,
            "description": self.description,
            "level": self.level,
        }


def create_starter_deck():
    return [
        Card(
            "strike",
            "타격",
            1,
            [{"type": "damage", "value": 8}],
            "적에게 8 피해",
            1,
        ),
        Card(
            "strike",
            "타격",
            1,
            [{"type": "damage", "value": 8}],
            "적에게 8 피해",
            1,
        ),
        Card(
            "defend",
            "수비",
            1,
            [{"type": "block", "value": 6}],
            "방어도 6 획득",
            1,
        ),
        Card(
            "defend",
            "수비",
            1,
            [{"type": "block", "value": 6}],
            "방어도 6 획득",
            1,
        ),
        Card(
            "fireball",
            "화염구",
            2,
            [{"type": "damage", "value": 18}],
            "강력한 18 피해",
            1,
        ),
    ]


class Monster:

    def __init__(self, name: str, hp: int, atk: int):
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.atk = atk

    def to_dict(self):
        return {
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "atk": self.atk,
        }


class GlobalBoss:

    def __init__(self, wave: int):
        self.wave = wave
        self.name = f"🔥 고대 파괴신 [Stage {wave}]"
        self.max_hp = 120 * wave
        self.hp = self.max_hp
        self.damage_dealt = {}

    def to_dict(self):
        return {
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "wave": self.wave,
            "damage_dealt": self.damage_dealt,
        }


class PlayerState:

    def __init__(self, player_id: str, deck: list):
        self.player_id = player_id
        self.hp = 100
        self.max_hp = 100
        self.energy = 3
        self.max_energy = 3
        self.block = 0
        self.buff_damage = 0
        self.deck = copy.deepcopy(deck)
        self.hand = copy.deepcopy(self.deck[:4])
        self.current_monster = Monster("야생의 슬라임", 30, 6)
        self.monsters_cleared = 0

    def next_turn(self):
        self.energy = self.max_energy
        self.block = 0


class SlayRaceGameEngine:

    def __init__(self, p1_id: str, p1_deck: list, p2_id: str, p2_deck: list):
        self.players = {
            p1_id: PlayerState(p1_id, p1_deck),
            p2_id: PlayerState(p2_id, p2_deck),
        }
        self.turn_count = 1
        self.global_boss = None
        self.boss_wave = 0
        self.game_over = False
        self.winner = None

    def play_card(self, player_id: str, card_instance_id: str):
        p = self.players[player_id]
        logs = []

        card = next((c for c in p.hand if c.instance_id == card_instance_id), None)
        if not card or card.cost > p.energy:
            return {"success": False, "logs": ["마나가 부족합니다."]}

        p.energy -= card.cost
        target_boss = self.global_boss is not None

        for eff in card.effects:
            if eff["type"] == "damage":
                dmg = eff["value"] + p.buff_damage
                if target_boss:
                    self.global_boss.hp -= dmg
                    self.global_boss.damage_dealt[player_id] = (
                        self.global_boss.damage_dealt.get(player_id, 0) + dmg
                    )
                    logs.append(
                        f"⚔️ {player_id}님이 [공동보스]에게 {dmg} 피해!"
                    )
                    if self.global_boss.hp <= 0:
                        logs.extend(self._resolve_boss_defeat())
                else:
                    p.current_monster.hp -= dmg
                    logs.append(
                        f"⚔️ {player_id}님이 [{p.current_monster.name}]에게 {dmg} 피해!"
                    )
                    if p.current_monster.hp <= 0:
                        p.monsters_cleared += 1
                        logs.append(
                            f"🏆 {player_id}님이 [{p.current_monster.name}] 처치!"
                        )
                        p.current_monster = Monster(
                            f"몬스터 Lv.{p.monsters_cleared + 1}",
                            30 + (p.monsters_cleared * 15),
                            6 + (p.monsters_cleared * 2),
                        )

            elif eff["type"] == "block":
                p.block += eff["value"]
                logs.append(
                    f"🛡️ {player_id}님이 방어도 {eff['value']}를 얻었습니다."
                )

        return {"success": True, "logs": logs}

    def merge_cards(self, player_id: str, base_id: str, level: int):
        p = self.players[player_id]
        matching = [
            c for c in p.hand if c.base_id == base_id and c.level == level
        ]

        if len(matching) < 2:
            return {"success": False, "logs": ["합성할 동일 카드가 부족합니다."]}

        c1, c2 = matching[0], matching[1]
        p.hand.remove(c1)
        p.hand.remove(c2)

        new_level = level + 1
        level_suffix = "+" if new_level == 2 else "++"
        new_name = f"{c1.name.replace('+', '').strip()} {level_suffix}"

        new_effects = []
        for eff in c1.effects:
            new_eff = copy.deepcopy(eff)
            new_eff["value"] = int(eff["value"] * 2.2)
            new_effects.append(new_eff)

        merged_card = Card(
            card_id=f"{base_id}_l{new_level}",
            name=new_name,
            cost=c1.cost,
            effects=new_effects,
            description=f"[합성 {level_suffix}] 강화된 효과",
            level=new_level,
            base_id=base_id,
        )

        p.hand.append(merged_card)
        return {
            "success": True,
            "logs": [f"✨ {player_id}님이 카드를 합성하여 [{new_name}] 획득!"],
        }

    def end_turn(self, player_id: str):
        p = self.players[player_id]
        logs = [f"🔄 {player_id} 턴 완료"]

        if p.current_monster and p.current_monster.hp > 0:
            dmg = max(0, p.current_monster.atk - p.block)
            p.hp -= dmg
            logs.append(
                f"💥 [{p.current_monster.name}]의 공격! {dmg} 피해를 받았습니다."
            )

        p.next_turn()
        self.turn_count += 1

        if self.turn_count % 10 == 0 and self.global_boss is None:
            self.boss_wave += 1
            self.global_boss = GlobalBoss(self.boss_wave)
            logs.append(
                f"🚨 [경고] 10턴 도달! {self.global_boss.name} 난입!"
            )

        if p.hp <= 0:
            self.game_over = True
            other_id = [pid for pid in self.players if pid != player_id][0]
            self.winner = other_id

        return {"success": True, "logs": logs}

    def _resolve_boss_defeat(self):
        logs = [f"🎉 공동 보스 {self.global_boss.name} 퇴치!"]
        damage_map = self.global_boss.damage_dealt

        if damage_map:
            winner_id = max(damage_map, key=damage_map.get)
            self.players[winner_id].buff_damage += 5
            logs.append(
                f"👑 최고 딜러 [{winner_id}]님이 공격력 +5 버프를 획득했습니다!"
            )

        self.global_boss = None
        return logs

    def get_game_state(self, player_id: str):
        me = self.players[player_id]
        opp_id = [pid for pid in self.players if pid != player_id][0]
        opp = self.players[opp_id]

        return {
            "turn_count": self.turn_count,
            "game_over": self.game_over,
            "winner": self.winner,
            "global_boss": (
                self.global_boss.to_dict() if self.global_boss else None
            ),
            "me": {
                "player_id": me.player_id,
                "hp": me.hp,
                "energy": me.energy,
                "block": me.block,
                "buff_damage": me.buff_damage,
                "monsters_cleared": me.monsters_cleared,
                "current_monster": (
                    me.current_monster.to_dict() if me.current_monster else None
                ),
                "hand": [c.to_dict() for c in me.hand],
            },
            "opponent": {
                "player_id": opp.player_id,
                "hp": opp.hp,
                "monsters_cleared": opp.monsters_cleared,
                "current_monster": (
                    opp.current_monster.to_dict()
                    if opp.current_monster
                    else None
                ),
            },
        }