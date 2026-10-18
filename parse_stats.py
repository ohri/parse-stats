#!/usr/bin/env python3
"""
Fantasy Football Stats Parser
Parses NFL play-by-play CSV data and generates SQL statements for database insertion.
"""

import csv
import sys
import argparse
import glob
import os
from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, List, DefaultDict
from collections import defaultdict


def expand_input_files(file_patterns: List[str]) -> List[str]:
    """Expand input paths and wildcard patterns into unique regular files."""
    input_files = []

    for pattern in file_patterns:
        matches = sorted(glob.glob(pattern))
        if not matches:
            raise FileNotFoundError(pattern)

        for match in matches:
            if os.path.isfile(match) and match not in input_files:
                input_files.append(match)

    if not input_files:
        raise FileNotFoundError(", ".join(file_patterns))

    return input_files


class PlayerStatTypes(IntEnum):
    """Player stat type IDs matching database schema"""
    CARRIES = 1
    RUSH_YARDS = 2
    RUSH_TDS = 5
    PASS_ATTEMPTS = 6
    PASS_COMPLETIONS = 7
    PASSING_YARDS = 8
    PASSING_TDS = 11
    INTERCEPTIONS_THROWN = 13
    RECEPTIONS = 15
    RECEIVING_YARDS = 16
    RECEIVING_TDS = 19
    INTERCEPTIONS = 20
    INTERCEPTION_RETURN_YARDS = 21
    INTERCEPTION_TOUCHDOWN = 24
    PUNTS = 25
    TOTAL_PUNT_YARDS = 26
    PUNT_AVERAGE = 27
    PUNT_TOUCHBACKS = 28
    PUNTS_INSIDE_20 = 29
    MADE_FIELD_GOAL_DISTANCE = 31
    PAT = 32
    PUNT_RETURN_YARDS = 34
    PUNT_RETURN_TDS = 38
    KICK_RETURN_YARDS = 46
    KICK_RETURN_TDS = 50
    FUMBLES = 57
    FUMBLE_RECOVERY = 58
    FUMBLE_RETURN_YARDS = 59
    FUMBLE_RETURN_TDS = 60
    FORCED_FUMBLES = 61
    TACKLES = 62
    ASSISTS = 63
    SACKS = 64
    PASSES_DEFENSED = 66
    BLOCKS = 67
    STUFFS = 68
    SAFETIES = 69
    TWO_POINT_CONVERSION_PASS = 70
    TWO_POINT_CONVERSION = 71
    FIELD_GOAL_MADE = 72
    FIELD_GOAL_ATTEMPTED = 73
    FUMBLES_LOST = 74
    QB_HITS = 76
    KICKOFF_TOUCHBACK = 77
    KICKOFF_OUT_OF_BOUNDS = 78
    MISC_DEFENSIVE_TD = 79


class TeamStatTypes(IntEnum):
    """Team stat type IDs (internal use, not database IDs)"""
    TEAM_RUSH_ATTEMPTS_LEFT = 1001
    TEAM_RUSH_ATTEMPTS_CENTER = 1002
    TEAM_RUSH_ATTEMPTS_RIGHT = 1003
    TEAM_RUSH_YARDS_LEFT = 1010
    TEAM_RUSH_YARDS_CENTER = 1011
    TEAM_RUSH_YARDS_RIGHT = 1012
    TEAM_RUSH_TDS = 1020
    TEAM_PASS_ATTEMPTS = 1030
    TEAM_SACKS_ALLOWED = 1031
    TEAM_PASS_YARDS = 1032


@dataclass
class FieldGoal:
    """Represents a field goal attempt"""
    distance: int
    made: bool


@dataclass
class Punt:
    """Represents a punt"""
    distance: int
    inside20: bool
    in_ez: bool


class DataParser:
    """Parses play-by-play data and extracts statistics"""

    def __init__(self):
        self.stats: DefaultDict[str, Dict[int, float]] = defaultdict(dict)
        self.kicks: DefaultDict[str, List[FieldGoal]] = defaultdict(list)
        self.punts: DefaultDict[str, List[Punt]] = defaultdict(list)

    @staticmethod
    def is_valid_value(value: str) -> bool:
        """Check if a value is valid (not NA or empty)"""
        return value not in ("NA", "", "na", "N/A")

    @staticmethod
    def safe_int(value: str, default: int = 0) -> int:
        """Safely parse an integer from a string"""
        if not DataParser.is_valid_value(value):
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    def add_stat(self, key: str, stat_id: int, value: float):
        """Add or increment a stat value"""
        if stat_id not in self.stats[key]:
            self.stats[key][stat_id] = value
        else:
            self.stats[key][stat_id] += value

    def route_parsing(self, play: Dict[str, str]):
        """Route play parsing based on play type"""
        # Skip plays with no stats
        if play.get("play_type_nfl") in ("GAME_START", "GAMES_START", "TIMEOUT", "END_QUARTER", "END_GAME"):
            return

        # Process different play types
        if play.get("rush_attempt") == "1" and play.get("play_type_nfl") != "PAT2" and play.get("play_type") != "no_play":
            self.look_for_run(play)
        elif play.get("pass") == "1" and play.get("play_type_nfl") != "PAT2" and play.get("play_type") != "no_play":
            self.look_for_pass(play)
        elif play.get("play_type") in ("kickoff", "field_goal", "extra_point"):
            self.look_for_kick(play)
        elif play.get("play_type") == "punt":
            self.look_for_punt(play)
        elif play.get("play_type_nfl") == "PAT2":
            self.look_for_2pat(play)

        # Always check for tackles and fumbles
        self.look_for_tackles(play)
        if play.get("fumble") == "1":
            self.look_for_fumbles(play)

    def look_for_run(self, play: Dict[str, str]):
        """Process rushing plays"""
        player = play.get("rusher_player_id", "")
        team = play.get("posteam", "")

        if not self.is_valid_value(player) or not self.is_valid_value(team):
            return

        self.add_stat(player, PlayerStatTypes.CARRIES, 1)

        # Touchdown?
        if play.get("rush_touchdown") == "1":
            self.add_stat(player, PlayerStatTypes.RUSH_TDS, 1)
            self.add_stat(team, TeamStatTypes.TEAM_RUSH_TDS, 1)

        # Yards
        rush_yards = self.safe_int(play.get("rushing_yards", "0"))
        self.add_stat(player, PlayerStatTypes.RUSH_YARDS, rush_yards)

        # Direction
        run_location = play.get("run_location", "middle")
        if run_location == "left":
            direction = TeamStatTypes.TEAM_RUSH_YARDS_LEFT
            direction_attempt = TeamStatTypes.TEAM_RUSH_ATTEMPTS_LEFT
        elif run_location == "right":
            direction = TeamStatTypes.TEAM_RUSH_YARDS_RIGHT
            direction_attempt = TeamStatTypes.TEAM_RUSH_ATTEMPTS_RIGHT
        else:  # middle or default
            direction = TeamStatTypes.TEAM_RUSH_YARDS_CENTER
            direction_attempt = TeamStatTypes.TEAM_RUSH_ATTEMPTS_CENTER

        self.add_stat(team, direction, rush_yards)
        self.add_stat(team, direction_attempt, 1)

    def look_for_pass(self, play: Dict[str, str]):
        """Process passing plays"""
        team = play.get("posteam", "")
        if not self.is_valid_value(team):
            return

        if play.get("pass_attempt") == "1":
            # Check for sacks
            if play.get("sack") == "1":
                for sack_field in ["sack_player_id", "half_sack_1_player_id", "half_sack_2_player_id"]:
                    p = play.get(sack_field, "")
                    if self.is_valid_value(p):
                        sack_value = 0.5 if "half" in sack_field else 1.0
                        self.add_stat(p, PlayerStatTypes.SACKS, sack_value)
                self.add_stat(team, TeamStatTypes.TEAM_SACKS_ALLOWED, 1)
            else:
                # Pass attempt
                passer = play.get("passer_player_id", "")
                if not self.is_valid_value(passer):
                    return

                self.add_stat(passer, PlayerStatTypes.PASS_ATTEMPTS, 1)
                self.add_stat(team, TeamStatTypes.TEAM_PASS_ATTEMPTS, 1)

                if play.get("complete_pass") == "1":
                    # Completion
                    receiver = play.get("receiver_player_id", "")
                    if self.is_valid_value(receiver):
                        self.add_stat(receiver, PlayerStatTypes.RECEPTIONS, 1)
                        receiving_yards = self.safe_int(play.get("receiving_yards", "0"))
                        self.add_stat(receiver, PlayerStatTypes.RECEIVING_YARDS, receiving_yards)

                        if play.get("pass_touchdown") == "1":
                            self.add_stat(receiver, PlayerStatTypes.RECEIVING_TDS, 1)
                            self.add_stat(passer, PlayerStatTypes.PASSING_TDS, 1)

                    self.add_stat(passer, PlayerStatTypes.PASS_COMPLETIONS, 1)
                    passing_yards = self.safe_int(play.get("passing_yards", "0"))
                    self.add_stat(passer, PlayerStatTypes.PASSING_YARDS, passing_yards)
                    self.add_stat(team, TeamStatTypes.TEAM_PASS_YARDS, passing_yards)

                elif play.get("interception") == "1":
                    # Interception
                    self.add_stat(passer, PlayerStatTypes.INTERCEPTIONS_THROWN, 1)

                    intercepter = play.get("interception_player_id", "")
                    if self.is_valid_value(intercepter):
                        self.add_stat(intercepter, PlayerStatTypes.INTERCEPTIONS, 1)
                        return_yards = self.safe_int(play.get("return_yards", "0"))
                        self.add_stat(intercepter, PlayerStatTypes.INTERCEPTION_RETURN_YARDS, return_yards)

                        if play.get("return_touchdown") == "1":
                            self.add_stat(intercepter, PlayerStatTypes.INTERCEPTION_TOUCHDOWN, 1)

            # Pass defense
            for pd_field in ["pass_defense_1_player_id", "pass_defense_2_player_id"]:
                p = play.get(pd_field, "")
                if self.is_valid_value(p):
                    self.add_stat(p, PlayerStatTypes.PASSES_DEFENSED, 1)

        # QB hits
        for qb_hit_field in ["qb_hit_1_player_id", "qb_hit_2_player_id"]:
            p = play.get(qb_hit_field, "")
            if self.is_valid_value(p):
                self.add_stat(p, PlayerStatTypes.QB_HITS, 1)

    def look_for_tackles(self, play: Dict[str, str]):
        """Process tackles"""
        # Determine if it's a stuff (tackle for loss or no gain)
        stuff = False
        if play.get("tackled_for_loss") == "1":
            stuff = True
        elif play.get("play_type") == "run" and self.safe_int(play.get("yards_gained", "0")) < 1:
            stuff = True
        elif play.get("play_type") == "pass":
            passing_yards = play.get("passing_yards", "")
            if self.is_valid_value(passing_yards) and self.safe_int(passing_yards) < 1:
                stuff = True

        # Safety
        safety_id = play.get("safety_player_id", "")
        if self.is_valid_value(safety_id):
            self.add_stat(safety_id, PlayerStatTypes.SAFETIES, 1)

        # Solo tackles
        if play.get("solo_tackle") == "1":
            p = play.get("solo_tackle_1_player_id", "")
            if self.is_valid_value(p):
                self.add_stat(p, PlayerStatTypes.TACKLES, 1)
                if stuff:
                    self.add_stat(p, PlayerStatTypes.STUFFS, 1)

        if self.is_valid_value(play.get("solo_tackle_2_team", "")):
            p = play.get("solo_tackle_2_player_id", "")
            if self.is_valid_value(p):
                self.add_stat(p, PlayerStatTypes.TACKLES, 1)
                if stuff:
                    self.add_stat(p, PlayerStatTypes.STUFFS, 1)

        # Assist tackles
        if play.get("assist_tackle") == "1":
            for assist_field in ["assist_tackle_1_player_id", "assist_tackle_2_player_id",
                                "assist_tackle_3_player_id", "assist_tackle_4_player_id"]:
                p = play.get(assist_field, "")
                if self.is_valid_value(p):
                    self.add_stat(p, PlayerStatTypes.ASSISTS, 1)
                    if stuff:
                        self.add_stat(p, PlayerStatTypes.STUFFS, 1)

            # Tackle with assist
            if play.get("tackle_with_assist") == "1":
                for twa_field in ["tackle_with_assist_1_player_id", "tackle_with_assist_2_player_id"]:
                    p = play.get(twa_field, "")
                    if self.is_valid_value(p):
                        self.add_stat(p, PlayerStatTypes.TACKLES, 1)
                        if stuff:
                            self.add_stat(p, PlayerStatTypes.STUFFS, 1)

    def look_for_fumbles(self, play: Dict[str, str]):
        """Process fumbles"""
        # Forced fumbles
        for ff_field in ["forced_fumble_player_1_player_id", "forced_fumble_player_2_player_id"]:
            p = play.get(ff_field, "")
            if self.is_valid_value(p):
                self.add_stat(p, PlayerStatTypes.FORCED_FUMBLES, 1)

        # Fumbles
        for fum_field in ["fumbled_1_player_id", "fumbled_2_player_id"]:
            p = play.get(fum_field, "")
            if self.is_valid_value(p):
                self.add_stat(p, PlayerStatTypes.FUMBLES, 1)
                if play.get("fumble_lost") == "1":
                    self.add_stat(p, PlayerStatTypes.FUMBLES_LOST, 1)

        # Fumble recoveries
        for i, fr_field in enumerate(["fumble_recovery_1_player_id", "fumble_recovery_2_player_id"], 1):
            p = play.get(fr_field, "")
            if self.is_valid_value(p):
                self.add_stat(p, PlayerStatTypes.FUMBLE_RECOVERY, 1)
                yards_field = f"fumble_recovery_{i}_yards"
                recovery_yards = self.safe_int(play.get(yards_field, "0"))
                self.add_stat(p, PlayerStatTypes.FUMBLE_RETURN_YARDS, recovery_yards)

                td_player = play.get("td_player_id", "")
                if self.is_valid_value(td_player):
                    self.add_stat(p, PlayerStatTypes.FUMBLE_RETURN_TDS, 1)

    def look_for_kick(self, play: Dict[str, str]):
        """Process kicks (PAT, kickoffs, field goals)"""
        p = play.get("kicker_player_id", "")
        if not self.is_valid_value(p):
            return

        # PAT
        if play.get("extra_point_attempt") == "1":
            if play.get("extra_point_result") == "good":
                self.add_stat(p, PlayerStatTypes.PAT, 1)
            elif play.get("extra_point_result") == "blocked":
                blocker = play.get("blocked_player_id", "")
                if self.is_valid_value(blocker):
                    self.add_stat(blocker, PlayerStatTypes.BLOCKS, 1)

        # Kickoffs
        elif play.get("play_type") == "kickoff":
            if play.get("touchback") == "1":
                self.add_stat(p, PlayerStatTypes.KICKOFF_TOUCHBACK, 1)
            elif play.get("kickoff_out_of_bounds") == "1":
                self.add_stat(p, PlayerStatTypes.KICKOFF_OUT_OF_BOUNDS, 1)
            else:
                returner = play.get("kickoff_returner_player_id", "")
                if self.is_valid_value(returner):
                    return_yards = self.safe_int(play.get("return_yards", "0"))
                    self.add_stat(returner, PlayerStatTypes.KICK_RETURN_YARDS, return_yards)
                    if play.get("return_touchdown") == "1":
                        self.add_stat(returner, PlayerStatTypes.KICK_RETURN_TDS, 1)

        # Field goals
        elif play.get("play_type") == "field_goal":
            distance = self.safe_int(play.get("kick_distance", "0"))
            made = play.get("field_goal_result") == "made"
            self.kicks[p].append(FieldGoal(distance, made))

            # Blocked?
            if play.get("field_goal_result") == "blocked":
                blocker = play.get("blocked_player_id", "")
                if self.is_valid_value(blocker):
                    self.add_stat(blocker, PlayerStatTypes.BLOCKS, 1)

                # Returned for score?
                td_player = play.get("td_player_id", "")
                if self.is_valid_value(td_player):
                    self.add_stat(td_player, PlayerStatTypes.MISC_DEFENSIVE_TD, 1)

    def look_for_punt(self, play: Dict[str, str]):
        """Process punts"""
        # The punt
        p = play.get("punter_player_id", "")
        if self.is_valid_value(p):
            inside20 = play.get("punt_inside_twenty") == "1"
            distance = self.safe_int(play.get("kick_distance", "0"))
            in_ez = False

            # Touchback means punt went into endzone
            if play.get("touchback") == "1":
                in_ez = True
                distance = self.safe_int(play.get("yardline_100", "0"))

            self.punts[p].append(Punt(distance, inside20, in_ez))

        # The return
        returner = play.get("punt_returner_player_id", "")
        if self.is_valid_value(returner):
            return_yards = self.safe_int(play.get("return_yards", "0"))
            self.add_stat(returner, PlayerStatTypes.PUNT_RETURN_YARDS, return_yards)
            if play.get("return_touchdown") == "1":
                self.add_stat(returner, PlayerStatTypes.PUNT_RETURN_TDS, 1)

        # Blocked punt
        if play.get("punt_blocked") == "1":
            blocker = play.get("blocked_player_id", "")
            if self.is_valid_value(blocker):
                self.add_stat(blocker, PlayerStatTypes.BLOCKS, 1)

            # Returned for TD?
            td_player = play.get("td_player_id", "")
            if self.is_valid_value(td_player):
                self.add_stat(td_player, PlayerStatTypes.MISC_DEFENSIVE_TD, 1)

    def look_for_2pat(self, play: Dict[str, str]):
        """Process 2-point conversions"""
        if play.get("two_point_conv_result") == "success":
            if play.get("play_type") == "run":
                p = play.get("rusher_player_id", "")
                if self.is_valid_value(p):
                    self.add_stat(p, PlayerStatTypes.TWO_POINT_CONVERSION, 1)
            elif play.get("play_type") == "pass":
                passer = play.get("passer_player_id", "")
                if self.is_valid_value(passer):
                    self.add_stat(passer, PlayerStatTypes.TWO_POINT_CONVERSION_PASS, 1)

                receiver = play.get("receiver_player_id", "")
                if self.is_valid_value(receiver):
                    self.add_stat(receiver, PlayerStatTypes.TWO_POINT_CONVERSION, 1)

    def reduce_punts(self):
        """Calculate aggregate punt statistics"""
        for player, punt_list in self.punts.items():
            num_punts = len(punt_list)
            punt_yards = sum(p.distance for p in punt_list)
            punt_touchbacks = sum(1 for p in punt_list if p.in_ez)
            punts_inside20 = sum(1 for p in punt_list if p.inside20)
            # Use integer division to match .NET behavior (int / int = int, then cast to double)
            punt_average = punt_yards // num_punts if num_punts > 0 else 0

            self.add_stat(player, PlayerStatTypes.PUNTS, num_punts)
            self.add_stat(player, PlayerStatTypes.TOTAL_PUNT_YARDS, punt_yards)
            self.add_stat(player, PlayerStatTypes.PUNT_TOUCHBACKS, punt_touchbacks)
            self.add_stat(player, PlayerStatTypes.PUNTS_INSIDE_20, punts_inside20)
            self.add_stat(player, PlayerStatTypes.PUNT_AVERAGE, punt_average)


class SQLGenerator:
    """Generates SQL statements from parsed statistics"""

    @staticmethod
    def write_stats(stats: Dict[str, Dict[int, float]], week: int, season: int):
        """Write player and team stats as SQL"""
        print("set serveroutput on;")
        print("--at end, search for 'Error starting at line'")
        print("--and 'Couldnt find player'")

        for player_id, stat_dict in stats.items():
            # Filter out invalid player IDs (NA or empty)
            # Also filter out 'NA' specifically to avoid the bug in the original code
            if not DataParser.is_valid_value(player_id) or player_id.upper() == 'NA':
                continue

            # Player stats (longer IDs)
            if len(player_id) > 4:
                for stat_id, value in stat_dict.items():
                    # Format value as int if it's a whole number
                    formatted_value = int(value) if value == int(value) else value
                    print(f"exec scoring.gsis_add_player_raw_stat( '{player_id}', {season}, {week}, {stat_id}, {formatted_value} );")

            # Team stats (2-4 letter abbreviations like LA, ATL, etc.)
            else:
                carries_left = stat_dict.get(TeamStatTypes.TEAM_RUSH_ATTEMPTS_LEFT, 0)
                carries_right = stat_dict.get(TeamStatTypes.TEAM_RUSH_ATTEMPTS_RIGHT, 0)
                carries_center = stat_dict.get(TeamStatTypes.TEAM_RUSH_ATTEMPTS_CENTER, 0)
                total_carries = carries_center + carries_left + carries_right

                yards_left = stat_dict.get(TeamStatTypes.TEAM_RUSH_YARDS_LEFT, 0)
                yards_right = stat_dict.get(TeamStatTypes.TEAM_RUSH_YARDS_RIGHT, 0)
                yards_center = stat_dict.get(TeamStatTypes.TEAM_RUSH_YARDS_CENTER, 0)
                total_rush_yards = yards_left + yards_right + yards_center

                rush_tds = stat_dict.get(TeamStatTypes.TEAM_RUSH_TDS, 0)
                pass_attempts = stat_dict.get(TeamStatTypes.TEAM_PASS_ATTEMPTS, 0)
                pass_yards = stat_dict.get(TeamStatTypes.TEAM_PASS_YARDS, 0)
                sacks_allowed = stat_dict.get(TeamStatTypes.TEAM_SACKS_ALLOWED, 0)

                # Format values as ints
                print(f"exec scoring.gsis_add_blocking_performance( '{player_id}', {season}, {week}, "
                      f"{int(total_carries)}, {int(total_rush_yards)}, {int(carries_center)}, {int(yards_center)}, "
                      f"{int(carries_left)}, {int(yards_left)}, {int(carries_right)}, {int(yards_right)}, "
                      f"{int(pass_attempts)}, {int(sacks_allowed)}, {int(pass_yards)}, {int(rush_tds)} );")

    @staticmethod
    def write_kicks(kicks: Dict[str, List[FieldGoal]], week: int, season: int):
        """Write field goal stats as SQL"""
        for player_id, fg_list in kicks.items():
            if not DataParser.is_valid_value(player_id) or player_id.upper() == 'NA':
                continue

            attempts = len(fg_list)
            made = sum(1 for fg in fg_list if fg.made)

            # Write made field goal distances
            for fg in fg_list:
                if fg.made:
                    print(f"exec scoring.gsis_add_player_raw_stat( '{player_id}', {season}, {week}, "
                          f"{PlayerStatTypes.MADE_FIELD_GOAL_DISTANCE}, {fg.distance} );")

            # Write attempts and made totals
            print(f"exec scoring.gsis_add_player_raw_stat( '{player_id}', {season}, {week}, "
                  f"{PlayerStatTypes.FIELD_GOAL_ATTEMPTED}, {attempts} );")
            print(f"exec scoring.gsis_add_player_raw_stat( '{player_id}', {season}, {week}, "
                  f"{PlayerStatTypes.FIELD_GOAL_MADE}, {made} );")


class PreScan:
    """Pre-scan CSV file for data integrity issues"""

    FIELDS_TO_CHECK = [
        ("rusher_player_id", "rusher_player_name", "rusher problem"),
        ("sack_player_id", "sack_player_name", "sack problem"),
        ("half_sack_1_player_id", "half_sack_1_player_name", "half_sack_1 problem"),
        ("half_sack_2_player_id", "half_sack_2_player_name", "half_sack_2 problem"),
        ("passer_player_id", "passer_player_name", "passer_player problem"),
        ("receiver_player_id", "receiver_player_name", "receiver_player problem"),
        ("interception_player_id", "interception_player_name", "interception_player problem"),
        ("pass_defense_1_player_id", "pass_defense_1_player_name", "pass_defense_1_player problem"),
        ("pass_defense_2_player_id", "pass_defense_2_player_name", "pass_defense_2_player problem"),
        ("qb_hit_1_player_id", "qb_hit_1_player_name", "qb_hit_1_player problem"),
        ("qb_hit_2_player_id", "qb_hit_2_player_name", "qb_hit_2_player problem"),
        ("solo_tackle_1_player_id", "solo_tackle_1_player_name", "solo_tackle_1_player problem"),
        ("solo_tackle_2_player_id", "solo_tackle_2_player_name", "solo_tackle_2_player problem"),
        ("assist_tackle_1_player_id", "assist_tackle_1_player_name", "assist_tackle_1_player problem"),
        ("assist_tackle_2_player_id", "assist_tackle_2_player_name", "assist_tackle_2_player problem"),
        ("assist_tackle_3_player_id", "assist_tackle_3_player_name", "assist_tackle_3_player problem"),
        ("assist_tackle_4_player_id", "assist_tackle_4_player_name", "assist_tackle_4_player problem"),
        ("tackle_with_assist_1_player_id", "tackle_with_assist_1_player_name", "tackle_with_assist_1_player problem"),
        ("tackle_with_assist_2_player_id", "tackle_with_assist_2_player_name", "tackle_with_assist_2_player problem"),
        ("forced_fumble_player_1_player_id", "forced_fumble_player_1_player_name", "forced_fumble_player_1_player problem"),
        ("forced_fumble_player_2_player_id", "forced_fumble_player_2_player_name", "forced_fumble_player_2_player problem"),
        ("fumbled_1_player_id", "fumbled_1_player_name", "fumbled_1_player problem"),
        ("fumbled_2_player_id", "fumbled_2_player_name", "fumbled_2_player problem"),
        ("fumble_recovery_1_player_id", "fumble_recovery_1_player_name", "fumble_recovery_1_player problem"),
        ("fumble_recovery_2_player_id", "fumble_recovery_2_player_name", "fumble_recovery_2_player problem"),
        ("kicker_player_id", "kicker_player_name", "kicker_player problem"),
        ("blocked_player_id", "blocked_player_name", "blocked_player problem"),
        ("kickoff_returner_player_id", "kickoff_returner_player_name", "kickoff_returner_player problem"),
        ("punter_player_id", "punter_player_name", "punter_player problem"),
        ("punt_returner_player_id", "punt_returner_player_name", "punt_returner_player problem"),
        ("td_player_id", "td_player_name", "td_player problem"),
        ("safety_player_id", "safety_player_name", "safety_player problem"),
    ]

    @staticmethod
    def are_same(id_val: str, name_val: str) -> bool:
        """Check if player ID and name are consistently filled or empty"""
        id_filled = DataParser.is_valid_value(id_val)
        name_filled = DataParser.is_valid_value(name_val)
        return id_filled == name_filled

    @staticmethod
    def scan_file(reader) -> bool:
        """Scan file for data integrity issues. Returns True if problems found."""
        found_problems = False

        for play in reader:
            if play.get("play_type") != "no_play":
                for id_field, name_field, error_msg in PreScan.FIELDS_TO_CHECK:
                    if not PreScan.are_same(play.get(id_field, ""), play.get(name_field, "")):
                        found_problems = True
                        print(f"Problem: Game {play.get('game_id', 'unknown')} "
                              f"Play {play.get('play_id', 'unknown')} -- {error_msg} "
                              f"{play.get(name_field, 'unknown')}", file=sys.stderr)

        return found_problems


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Parse NFL play-by-play data and generate SQL for fantasy stats',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '-f', '--file', required=True, nargs='+', dest='files',
        help='Input CSV file path(s) or wildcard pattern(s)'
    )
    parser.add_argument('-s', '--season', type=int, required=True, help='Season year')
    parser.add_argument('-w', '--week', type=int, required=True, help='Week number')
    parser.add_argument('-o', '--output', help='Output SQL file path (default: same as input with .sql extension)')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    try:
        input_files = expand_input_files(args.files)
    except FileNotFoundError as e:
        print(f"Error: No input files matched '{e.args[0]}'", file=sys.stderr)
        return 1

    # Determine output file path
    if args.output:
        output_file = args.output
    elif len(input_files) > 1:
        print("Error: --output is required when multiple input files are provided",
              file=sys.stderr)
        return 1
    else:
        # Replace .csv extension with .sql
        base_name = os.path.splitext(input_files[0])[0]
        output_file = f"{base_name}.sql"

    # Read CSV files
    csv_contents = []
    try:
        for input_file in input_files:
            with open(input_file, 'r', encoding='utf-8') as f:
                csv_contents.append((input_file, f.read()))
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    # Pre-scan for data integrity
    for _, csv_content in csv_contents:
        csv_lines = csv_content.splitlines()
        reader = csv.DictReader(csv_lines)
        if PreScan.scan_file(reader):
            print("Problems in data - terminating", file=sys.stderr)
            return 1

    # Parse the data
    data_parser = DataParser()
    for _, csv_content in csv_contents:
        csv_lines = csv_content.splitlines()
        reader = csv.DictReader(csv_lines)

        for play in reader:
            if int(play.get("week", "0")) == args.week:
                try:
                    data_parser.route_parsing(play)
                except Exception as e:
                    print(f"Exception occurred at play_id:{play.get('play_id', 'unknown')} -- {e}",
                          file=sys.stderr)

    # Reduce punt data
    data_parser.reduce_punts()

    # Generate SQL output
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Redirect stdout to file
            old_stdout = sys.stdout
            sys.stdout = f

            SQLGenerator.write_stats(data_parser.stats, args.week, args.season)
            SQLGenerator.write_kicks(data_parser.kicks, args.week, args.season)

            sys.stdout = old_stdout

        print(f"Successfully generated: {output_file}", file=sys.stderr)
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        return 1

    # Debug output
    if args.debug:
        print("\n\n--- DEBUG OUTPUT ---", file=sys.stderr)
        for player_id, stats in data_parser.stats.items():
            print(f"\n{player_id}:", file=sys.stderr)
            for stat_id, value in stats.items():
                print(f"\t{stat_id}\t{value}", file=sys.stderr)

        for player_id, fg_list in data_parser.kicks.items():
            print(f"\n{player_id} (FGs):", file=sys.stderr)
            for fg in fg_list:
                print(f"\t{fg.distance} yards\tmade:{fg.made}", file=sys.stderr)

        for player_id, punt_list in data_parser.punts.items():
            print(f"\n{player_id} (Punts):", file=sys.stderr)
            for punt in punt_list:
                print(f"\t{punt.distance}\tEZ?:{punt.in_ez}\t20?:{punt.inside20}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
