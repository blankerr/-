import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from slay_race_engine import Card, SlayRaceGameEngine, create_starter_deck

app = FastAPI()


@app.get("/")
async def get_client():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


class AIBot:

    def __init__(self, ai_id: str, engine: SlayRaceGameEngine):
        self.ai_id = ai_id
        self.engine = engine

    async def play_turn(self, broadcast_callback):
        await asyncio.sleep(0.4)
        ai = self.engine.players[self.ai_id]

        # 카드 합성
        base_ids = set(c.base_id for c in ai.hand)
        for b_id in base_ids:
            for lvl in [1, 2]:
                matching = [
                    c for c in ai.hand if c.base_id == b_id and c.level == lvl
                ]
                if len(matching) >= 2:
                    res = self.engine.merge_cards(self.ai_id, b_id, lvl)
                    await broadcast_callback(res.get("logs", []))
                    await asyncio.sleep(0.2)

        # 마나 범위 내 연속 플레이
        while True:
            playable = [c for c in ai.hand if c.cost <= ai.energy]
            if not playable or self.engine.game_over:
                break

            target_card = random.choice(playable)
            res = self.engine.play_card(self.ai_id, target_card.instance_id)
            await broadcast_callback(res.get("logs", []))
            await asyncio.sleep(0.3)

        if not self.engine.game_over:
            res = self.engine.end_turn(self.ai_id)
            await broadcast_callback(res.get("logs", []))


@app.websocket("/ws/race/{player_id}")
async def race_websocket(websocket: WebSocket, player_id: str):
    await websocket.accept()

    ai_id = "AI_Rival"
    engine = SlayRaceGameEngine(
        player_id, create_starter_deck(), ai_id, create_starter_deck()
    )
    bot = AIBot(ai_id, engine)

    turn_timer_task = None
    time_remaining = 30

    async def broadcast_state(logs: list = None, reset_timer: bool = False):
        nonlocal time_remaining
        if reset_timer:
            time_remaining = 30

        state = engine.get_game_state(player_id)
        state["time_remaining"] = time_remaining
        payload = {"type": "state_update", "state": state, "logs": logs or []}
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    async def turn_timer_loop():
        nonlocal time_remaining
        while not engine.game_over:
            await asyncio.sleep(1)
            time_remaining -= 1
            if time_remaining <= 0:
                # 30초 도달 시 자동 턴 종료
                res = engine.end_turn(player_id)
                await broadcast_state(
                    res.get("logs", [])
                    + ["⏰ 30초 시간 초과! 자동으로 턴이 종료되었습니다."],
                    reset_timer=True,
                )
                if not engine.game_over:
                    await bot.play_turn(broadcast_state)
                    time_remaining = 30
            else:
                await broadcast_state()

    turn_timer_task = asyncio.task = asyncio.create_task(turn_timer_loop())
    await broadcast_state(["⚡ 30초 타이머 실시간 카드 레이스가 시작되었습니다!"], True)

    try:
        while True:
            data = await websocket.receive_json()
            act = data.get("action")

            if engine.game_over:
                continue

            if act == "play_card":
                res = engine.play_card(player_id, data.get("card_instance_id"))
                await broadcast_state(res.get("logs", []))

            elif act == "merge_cards":
                res = engine.merge_cards(
                    player_id, data.get("base_id"), data.get("level")
                )
                await broadcast_state(res.get("logs", []))

            elif act == "end_turn":
                # 플레이어가 수동으로 턴 종료 버튼 누름
                res = engine.end_turn(player_id)
                await broadcast_state(res.get("logs", []), reset_timer=True)

                if not engine.game_over:
                    await bot.play_turn(broadcast_state)
                    time_remaining = 30

    except WebSocketDisconnect:
        if turn_timer_task:
            turn_timer_task.cancel()