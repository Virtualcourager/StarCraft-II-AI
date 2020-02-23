import sc2
import random
from sc2.constants import NEXUS,PROBE,PYLON,ASSIMILATOR,GATEWAY,CYBERNETICSCORE,STALKER,STARGATE,VOIDRAY,ADEPT,ZEALOT
from sc2.player import Bot, Computer
from sc2 import run_game, maps, Race, Difficulty
from sc2.unit import Unit
from sc2.position import Point2, Point3
from sc2.ids.unit_typeid import UnitTypeId
from typing import Union

#165 iteration per minute
class sentdeBot(sc2.BotAI):
    def __init__(self):
        self.ITERATIONS_PER_MINUTE=165
        self.MAX_WORKERS=80
        self.WORKER_FLAG=0
        self.PYLON_FLAG = 0

    async def on_step(self, iteration):
        self.iteration=iteration
        await self.distribute_workers()
        await self.build_workers()
        await self.build_pylons()
        await self.rush()
        await self.offensive_force_buildings()
        await self.build_assimilators()
        await self.expand()
        await self.build_offensive_force()
        await self.attack()
        await self.stalker_micro(actions=[])

    async def build_workers(self):
        if (len(self.units(NEXUS))-1) * 16 + 22 > len(self.units(PROBE)) and len(self.units(PROBE))<self.MAX_WORKERS:
            for nexus in self.units(NEXUS).ready.noqueue:
                if self.can_afford(PROBE):
                    await self.do(nexus.train(PROBE))

    async def build_pylons(self):
        if self.supply_left<5 and not self.already_pending(PYLON):
            nexuses=self.units(NEXUS).ready
            if nexuses.exists:
                if self.can_afford(PYLON):
                    await self.build(PYLON,near=nexuses.random.position.towards(self.game_info.map_center, 10))

    async def rush(self):
        p = self.game_info.map_center.towards(self.enemy_start_locations[0], 10)
        worker = self.select_build_worker(p)
        if self.WORKER_FLAG==0 and self.can_afford(PYLON):
            self.WORKER_FLAG = worker.tag
            await self.build(PYLON, near=p)

    async def offensive_force_buildings(self):
        p = self.game_info.map_center.towards(self.enemy_start_locations[0], 10)
        c = self.units(NEXUS).ready.random.position.towards(self.game_info.map_center, 10)
        if self.units(PYLON).ready.exists:
            if self.units(GATEWAY).ready.exists and not self.units(CYBERNETICSCORE):
                if self.can_afford(CYBERNETICSCORE) and not self.already_pending(CYBERNETICSCORE):
                    await self.build(CYBERNETICSCORE,near=c)

            elif len(self.units(GATEWAY))+ self.already_pending(GATEWAY)<4:
                if self.can_afford(GATEWAY):
                    await self.build(GATEWAY,near=p)

    async def expand(self):
        if self.units(NEXUS).amount< (self.iteration/self.ITERATIONS_PER_MINUTE)/5 and self.can_afford(NEXUS):
            await self.expand_now()
        elif (self.units(NEXUS).amount<2 and self.supply_used>50) :
            await self.expand_now()
        elif self.minerals>=1200:
            await self.expand_now()

    async def build_assimilators(self):
        for nexus in self.units(NEXUS).ready:
            vaspenes=self.state.vespene_geyser.closer_than(10.0,nexus)
            for vaspene in vaspenes:
                if not self.can_afford(ASSIMILATOR):
                    break
                worker=self.select_build_worker(vaspene.position)
                if worker is None:
                    break
                if not self.units(ASSIMILATOR).closer_than(1.0,vaspene).exists:
                    await self.do(worker.build(ASSIMILATOR,vaspene))

    async def build_offensive_force(self):
        for gw in self.units(GATEWAY).ready.noqueue:
            if self.units(CYBERNETICSCORE).ready:
                if (self.can_afford(STALKER) and self.supply_used - self.supply_workers < 40):
                    await self.do(gw.train(STALKER))

    def find_target(self,state):
        if len(self.known_enemy_units) > 0:
            return random.choice(self.known_enemy_units)
        elif len(self.known_enemy_structures)> 0:
            return random.choice(self.known_enemy_structures)
        else:
            return self.enemy_start_locations[0]

    async def attack(self):
        aggresive_units={STALKER,ADEPT}
        if self.supply_used-self.supply_workers > 25:
            for UNIT in aggresive_units:
                for s in self.units(UNIT).idle:
                    await self.do(s.attack(self.find_target(self.state)))

    async def stalker_micro(self, actions):
        for unit in self.units(UnitTypeId.STALKER):

            if self.known_enemy_units:
                if unit.weapon_cooldown <= self._client.game_step / 2:
                    enemies_in_range = self.known_enemy_units.filter(lambda u: unit.target_in_range(u))
                    if enemies_in_range:
                        filtered_enemies_in_range = enemies_in_range.of_type(UnitTypeId.BANELING)

                        if not filtered_enemies_in_range:
                            closest_enemy = self.known_enemy_units.closest_to(unit)
                            actions.append(unit.attack(closest_enemy))
                        else:
                            actions.append(unit.attack(filtered_enemies_in_range))
                    else:
                        closest_enemy = self.known_enemy_units.closest_to(unit)
                        actions.append(unit.attack(closest_enemy))
                else:
                    stutter_step_positions = self.position_around_unit(unit, distance=6)
                    stutter_step_positions = {p for p in stutter_step_positions if self.in_pathing_grid(p)}

                    enemies_in_range = self.known_enemy_units.filter(lambda u: unit.target_in_range(u, -0.5))

                    if stutter_step_positions and enemies_in_range:
                        retreat_position = max(stutter_step_positions,
                                               key=lambda x: x.distance_to(enemies_in_range.center) - x.distance_to(
                                                   unit))
                        actions.append(unit.move(retreat_position))
                    else:
                        print("No retreat positions detected for unit {} at {}.".format(unit, unit.position.rounded))
        await self.do_actions(actions)



    def position_around_unit(self, pos: Union[Unit, Point2, Point3], distance: int = 1, step_size: int = 1, exclude_out_of_bounds: bool = True):
        pos = pos.position.to2.rounded
        positions = {pos.offset(Point2((x, y)))
                     for x in range(-distance, distance + 1, step_size)
                     for y in range(-distance, distance + 1, step_size)
                     if (x, y) != (0, 0)}
        if exclude_out_of_bounds:
            positions = {p for p in positions if 0 <= p[0] < self._game_info.pathing_grid.width and 0 <= p[1] < self._game_info.pathing_grid.height}
        return positions


run_game(maps.get("ThunderbirdLE"),[
        Bot(Race.Protoss,sentdeBot()),
        Computer(Race.Zerg, Difficulty.CheatInsane)
        ],realtime=False)
