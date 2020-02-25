import sc2
from sc2.player import Bot, Computer
from sc2 import run_game, maps, Race, Difficulty
from sc2.units import Units
from sc2.unit import Unit
from sc2.position import Point2, Point3
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.constants import COMMANDCENTER,MARINE,BARRACKS, SUPPLYDEPOT, SCV, UPGRADETOORBITAL_ORBITALCOMMAND, ORBITALCOMMAND, CALLDOWNMULE_CALLDOWNMULE
from sc2.ids.buff_id import BuffId
from sc2.ids.ability_id import AbilityId
from sc2.helpers import ControlGroup
from typing import Union

class fivebb(sc2.BotAI):
    def __init__(self):
        self.attack_groups =set()
        self.max_worker=80
        self.ITERATIONS_PER_MINUTE=165

    async def on_step(self, iteration):
        self.iteration = iteration
        await self.distribute_workers()
        await self.build_workers()
        await self.build_supply()
        await self.offensive_force_buildings()
        await self.build_offensive_force()
        await self.attack()
        await self.addattackgroup()
        await self.marine_micro(actions=[])
        await self.upgrade_orbit()
        await self.expand()
        await self.call_mule()

    async def addattackgroup(self):
        if self.units(MARINE).amount > 25:
            ad = ControlGroup(self.units(MARINE).idle)
            self.attack_groups.add(ad)
        elif self.units(MARINE).idle.amount > 15:
            ad = ControlGroup(self.units(MARINE).idle)
            self.attack_groups.add(ad)

    async def build_workers(self):
        if self.units(COMMANDCENTER).ready.exists:
            for cc in self.units(COMMANDCENTER).noqueue:
                if self.can_afford(SCV) and self.workers.amount < (self.units(COMMANDCENTER).amount+self.units(ORBITALCOMMAND).amount)*16 and self.workers.amount<self.max_worker:
                    if not self.units(BARRACKS).ready.exists:
                        await self.do(cc.train(SCV))
        elif self.units(ORBITALCOMMAND).ready.exists:
            for cc in self.units(ORBITALCOMMAND).noqueue:
                if self.can_afford(SCV) and self.workers.amount < (self.units(COMMANDCENTER).amount+self.units(ORBITALCOMMAND).amount)*16 and self.workers.amount<self.max_worker:
                    await self.do(cc.train(SCV))

    async def build_supply(self):
        if self.supply_left < max(self.units(BARRACKS).amount, 2):
            if self.can_afford(SUPPLYDEPOT) and not self.already_pending(SUPPLYDEPOT):
                if self.units(ORBITALCOMMAND).ready.exists:
                    cc = self.units(ORBITALCOMMAND).random
                else:
                    cc = self.units(COMMANDCENTER).random
                await self.build(SUPPLYDEPOT, near=cc.position.towards(self.game_info.map_center, 5))

    async def offensive_force_buildings(self):
        if self.units(BARRACKS).amount < 3 or (self.minerals > 400 and self.units(BARRACKS).amount < 5):
            if self.can_afford(BARRACKS):
                p = self.game_info.map_center.towards(self.enemy_start_locations[0], 15)
                await self.build(BARRACKS, near=p)
        if self.minerals > 500 and self.units(BARRACKS).amount < 10:
            if self.can_afford(BARRACKS):
                p = self.game_info.map_center.towards(self.enemy_start_locations[0], 20)
                await self.build(BARRACKS, near=p)

    async def build_offensive_force(self):
        for bb in self.units(BARRACKS).ready.noqueue:
            if not self.can_afford(MARINE):
                break
            elif self.units(MARINE).amount > self.units(SCV).amount* 2:
                break
            await self.do(bb.train(MARINE))

    async def attack(self):
        for ac in list(self.attack_groups):
            alive_units = ac.select_units(self.units)
            if alive_units.exists and alive_units.idle.exists:
                target = self.known_enemy_structures.random_or(self.enemy_start_locations[0]).position
                for marine in ac.select_units(self.units):
                    await self.do(marine.attack(target))
            else:
                self.attack_groups.remove(ac)

    async def upgrade_orbit(self):
        if self.units(BARRACKS).ready.exists:
            if self.can_afford(AbilityId.UPGRADETOORBITAL_ORBITALCOMMAND) and self.units(COMMANDCENTER).ready.exists:
                cc = self.units(COMMANDCENTER).random
                await self.do(cc(UPGRADETOORBITAL_ORBITALCOMMAND))

    async def call_mule(self):
        if self.units(ORBITALCOMMAND).ready.exists:
            for oc in self.units(ORBITALCOMMAND):
                abilities = await self.get_available_abilities(oc)
                if AbilityId.CALLDOWNMULE_CALLDOWNMULE in abilities:
                    await self.do(oc(CALLDOWNMULE_CALLDOWNMULE, self.state.mineral_field.closest_to(oc)))

    async def marine_micro(self, actions):
        for unit in self.units(UnitTypeId.MARINE):
            if self.known_enemy_units:
                if unit.weapon_cooldown <= self._client.game_step / 2:
                    enemies_in_range = self.known_enemy_units.filter(lambda u: unit.target_in_range(u))
                    if enemies_in_range:
                            closest_enemy = self.known_enemy_units.closest_to(unit)
                            actions.append(unit.attack(closest_enemy))
                    else:
                        closest_enemy = self.known_enemy_units.closest_to(unit)
                        actions.append(unit.attack(closest_enemy))
                else:
                    stutter_step_positions = self.position_around_unit(unit, distance=5)
                    stutter_step_positions = {p for p in stutter_step_positions if self.in_pathing_grid(p)}
                    enemies_in_range = self.known_enemy_units.filter(lambda u: unit.target_in_range(u, -0.5))
                    if stutter_step_positions and enemies_in_range:
                        retreat_position = max(stutter_step_positions,
                                               key=lambda x: x.distance_to(enemies_in_range.center) - x.distance_to(
                                                   unit))
                        actions.append(unit.move(retreat_position))
        await self.do_actions(actions)

    def position_around_unit(self, pos: Union[Unit, Point2, Point3], distance: int = 1, step_size: int = 1,
                             exclude_out_of_bounds: bool = True):
        pos = pos.position.to2.rounded
        positions = {pos.offset(Point2((x, y)))
                     for x in range(-distance, distance + 1, step_size)
                     for y in range(-distance, distance + 1, step_size)
                     if (x, y) != (0, 0)}
        # filter positions outside map size
        if exclude_out_of_bounds:
            positions = {p for p in positions if 0 <= p[0] < self._game_info.pathing_grid.width and 0 <= p[
                1] < self._game_info.pathing_grid.height}
        return positions

    async def expand(self):
        if self.units(COMMANDCENTER).amount+self.units(ORBITALCOMMAND).amount< (self.iteration/self.ITERATIONS_PER_MINUTE)*4 and self.can_afford(COMMANDCENTER) and not self.already_pending(COMMANDCENTER) :
            await self.expand_now()
        if self.minerals > 700 and self.can_afford(COMMANDCENTER) and not self.already_pending(COMMANDCENTER):
            await self.expand()

run_game(maps.get("ThunderbirdLE"), [
        Bot(Race.Terran, fivebb()),
        Computer(Race.Protoss, Difficulty.CheatInsane)
    ], realtime=False)

