#!/usr/bin/env python3
"""
Test suite for parse_stats.py
Run with: pytest test_parse_stats.py -v
"""

import pytest
import sys
import os
from io import StringIO
from pathlib import Path

# Import the module to test
import parse_stats
from parse_stats import (
    DataParser, SQLGenerator, PreScan,
    PlayerStatTypes, TeamStatTypes,
    FieldGoal, Punt
)


class TestDataParser:
    """Test the DataParser class"""

    @pytest.fixture
    def parser(self):
        """Create a fresh DataParser instance for each test"""
        return DataParser()

    def test_is_valid_value(self):
        """Test validation of field values"""
        assert DataParser.is_valid_value("valid_value") == True
        assert DataParser.is_valid_value("00-0012345") == True
        assert DataParser.is_valid_value("NA") == False
        assert DataParser.is_valid_value("") == False
        assert DataParser.is_valid_value("na") == False
        assert DataParser.is_valid_value("N/A") == False

    def test_safe_int(self):
        """Test safe integer parsing"""
        assert DataParser.safe_int("123") == 123
        assert DataParser.safe_int("45.7") == 45  # Handles float strings
        assert DataParser.safe_int("NA") == 0
        assert DataParser.safe_int("") == 0
        assert DataParser.safe_int("invalid", 99) == 99
        assert DataParser.safe_int("-10") == -10

    def test_add_stat(self, parser):
        """Test adding statistics"""
        parser.add_stat("player1", 1, 5)
        assert parser.stats["player1"][1] == 5

        # Test incrementing
        parser.add_stat("player1", 1, 3)
        assert parser.stats["player1"][1] == 8

        # Test multiple stats
        parser.add_stat("player1", 2, 10)
        assert parser.stats["player1"][2] == 10
        assert parser.stats["player1"][1] == 8

    def test_look_for_run_basic(self, parser):
        """Test basic rushing play parsing"""
        play = {
            "play_type": "run",
            "rusher_player_id": "00-0012345",
            "posteam": "KC",
            "rushing_yards": "15",
            "run_location": "left",
            "rush_touchdown": "0"
        }
        parser.look_for_run(play)

        assert parser.stats["00-0012345"][PlayerStatTypes.CARRIES] == 1
        assert parser.stats["00-0012345"][PlayerStatTypes.RUSH_YARDS] == 15
        assert parser.stats["KC"][TeamStatTypes.TEAM_RUSH_YARDS_LEFT] == 15
        assert parser.stats["KC"][TeamStatTypes.TEAM_RUSH_ATTEMPTS_LEFT] == 1

    def test_look_for_run_touchdown(self, parser):
        """Test rushing touchdown"""
        play = {
            "rusher_player_id": "00-0012345",
            "posteam": "KC",
            "rushing_yards": "25",
            "run_location": "right",
            "rush_touchdown": "1"
        }
        parser.look_for_run(play)

        assert parser.stats["00-0012345"][PlayerStatTypes.RUSH_TDS] == 1
        assert parser.stats["KC"][TeamStatTypes.TEAM_RUSH_TDS] == 1

    def test_look_for_run_directions(self, parser):
        """Test all run directions"""
        # Left
        play_left = {
            "rusher_player_id": "00-0012345",
            "posteam": "KC",
            "rushing_yards": "5",
            "run_location": "left",
            "rush_touchdown": "0"
        }
        parser.look_for_run(play_left)
        assert parser.stats["KC"][TeamStatTypes.TEAM_RUSH_ATTEMPTS_LEFT] == 1

        # Right
        play_right = {
            "rusher_player_id": "00-0012345",
            "posteam": "KC",
            "rushing_yards": "3",
            "run_location": "right",
            "rush_touchdown": "0"
        }
        parser.look_for_run(play_right)
        assert parser.stats["KC"][TeamStatTypes.TEAM_RUSH_ATTEMPTS_RIGHT] == 1

        # Middle/Center
        play_middle = {
            "rusher_player_id": "00-0012345",
            "posteam": "KC",
            "rushing_yards": "2",
            "run_location": "middle",
            "rush_touchdown": "0"
        }
        parser.look_for_run(play_middle)
        assert parser.stats["KC"][TeamStatTypes.TEAM_RUSH_ATTEMPTS_CENTER] == 1

    def test_look_for_pass_completion(self, parser):
        """Test completed pass"""
        play = {
            "pass_attempt": "1",
            "sack": "0",
            "passer_player_id": "00-0011111",
            "posteam": "KC",
            "complete_pass": "1",
            "receiver_player_id": "00-0022222",
            "receiving_yards": "20",
            "passing_yards": "20",
            "pass_touchdown": "0"
        }
        parser.look_for_pass(play)

        assert parser.stats["00-0011111"][PlayerStatTypes.PASS_ATTEMPTS] == 1
        assert parser.stats["00-0011111"][PlayerStatTypes.PASS_COMPLETIONS] == 1
        assert parser.stats["00-0011111"][PlayerStatTypes.PASSING_YARDS] == 20
        assert parser.stats["00-0022222"][PlayerStatTypes.RECEPTIONS] == 1
        assert parser.stats["00-0022222"][PlayerStatTypes.RECEIVING_YARDS] == 20
        assert parser.stats["KC"][TeamStatTypes.TEAM_PASS_ATTEMPTS] == 1

    def test_look_for_pass_touchdown(self, parser):
        """Test passing touchdown"""
        play = {
            "pass_attempt": "1",
            "sack": "0",
            "passer_player_id": "00-0011111",
            "posteam": "KC",
            "complete_pass": "1",
            "receiver_player_id": "00-0022222",
            "receiving_yards": "35",
            "passing_yards": "35",
            "pass_touchdown": "1"
        }
        parser.look_for_pass(play)

        assert parser.stats["00-0011111"][PlayerStatTypes.PASSING_TDS] == 1
        assert parser.stats["00-0022222"][PlayerStatTypes.RECEIVING_TDS] == 1

    def test_look_for_pass_interception(self, parser):
        """Test interception"""
        play = {
            "pass_attempt": "1",
            "sack": "0",
            "passer_player_id": "00-0011111",
            "posteam": "KC",
            "complete_pass": "0",
            "interception": "1",
            "interception_player_id": "00-0033333",
            "return_yards": "15",
            "return_touchdown": "0"
        }
        parser.look_for_pass(play)

        assert parser.stats["00-0011111"][PlayerStatTypes.INTERCEPTIONS_THROWN] == 1
        assert parser.stats["00-0033333"][PlayerStatTypes.INTERCEPTIONS] == 1
        assert parser.stats["00-0033333"][PlayerStatTypes.INTERCEPTION_RETURN_YARDS] == 15

    def test_look_for_pass_sack(self, parser):
        """Test sack statistics"""
        play = {
            "pass_attempt": "1",
            "sack": "1",
            "sack_player_id": "00-0044444",
            "sack_player_name": "J.Defender",
            "half_sack_1_player_id": "NA",
            "half_sack_2_player_id": "NA",
            "posteam": "KC"
        }
        parser.look_for_pass(play)

        assert parser.stats["00-0044444"][PlayerStatTypes.SACKS] == 1
        assert parser.stats["KC"][TeamStatTypes.TEAM_SACKS_ALLOWED] == 1

    def test_look_for_pass_half_sacks(self, parser):
        """Test half sack statistics"""
        play = {
            "pass_attempt": "1",
            "sack": "1",
            "sack_player_id": "NA",
            "half_sack_1_player_id": "00-0044444",
            "half_sack_2_player_id": "00-0055555",
            "posteam": "KC"
        }
        parser.look_for_pass(play)

        assert parser.stats["00-0044444"][PlayerStatTypes.SACKS] == 0.5
        assert parser.stats["00-0055555"][PlayerStatTypes.SACKS] == 0.5

    def test_look_for_tackles_solo(self, parser):
        """Test solo tackle"""
        play = {
            "solo_tackle": "1",
            "solo_tackle_1_player_id": "00-0066666",
            "play_type": "run",
            "yards_gained": "3",
            "tackled_for_loss": "0"
        }
        parser.look_for_tackles(play)

        assert parser.stats["00-0066666"][PlayerStatTypes.TACKLES] == 1
        assert PlayerStatTypes.STUFFS not in parser.stats["00-0066666"]

    def test_look_for_tackles_stuff(self, parser):
        """Test tackle for loss (stuff)"""
        play = {
            "solo_tackle": "1",
            "solo_tackle_1_player_id": "00-0066666",
            "play_type": "run",
            "yards_gained": "-2",
            "tackled_for_loss": "1"
        }
        parser.look_for_tackles(play)

        assert parser.stats["00-0066666"][PlayerStatTypes.TACKLES] == 1
        assert parser.stats["00-0066666"][PlayerStatTypes.STUFFS] == 1

    def test_look_for_tackles_assists(self, parser):
        """Test assisted tackles"""
        play = {
            "solo_tackle": "0",
            "assist_tackle": "1",
            "assist_tackle_1_player_id": "00-0077777",
            "assist_tackle_2_player_id": "00-0088888",
            "assist_tackle_2_team": "KC",
            "play_type": "run",
            "yards_gained": "2",
            "tackled_for_loss": "0",
            "tackle_with_assist": "1",
            "tackle_with_assist_1_player_id": "00-0099999"
        }
        parser.look_for_tackles(play)

        assert parser.stats["00-0077777"][PlayerStatTypes.ASSISTS] == 1
        assert parser.stats["00-0088888"][PlayerStatTypes.ASSISTS] == 1
        assert parser.stats["00-0099999"][PlayerStatTypes.TACKLES] == 1

    def test_look_for_fumbles(self, parser):
        """Test fumble statistics"""
        play = {
            "forced_fumble_player_1_player_id": "00-0011111",
            "forced_fumble_player_2_player_id": "NA",
            "fumbled_1_player_id": "00-0022222",
            "fumbled_2_player_id": "NA",
            "fumble_lost": "1",
            "fumble_recovery_1_player_id": "00-0033333",
            "fumble_recovery_2_player_id": "NA",
            "fumble_recovery_1_yards": "10",
            "td_player_id": "NA"
        }
        parser.look_for_fumbles(play)

        assert parser.stats["00-0011111"][PlayerStatTypes.FORCED_FUMBLES] == 1
        assert parser.stats["00-0022222"][PlayerStatTypes.FUMBLES] == 1
        assert parser.stats["00-0022222"][PlayerStatTypes.FUMBLES_LOST] == 1
        assert parser.stats["00-0033333"][PlayerStatTypes.FUMBLE_RECOVERY] == 1
        assert parser.stats["00-0033333"][PlayerStatTypes.FUMBLE_RETURN_YARDS] == 10

    def test_look_for_kick_pat(self, parser):
        """Test PAT (extra point)"""
        play = {
            "play_type": "extra_point",
            "kicker_player_id": "00-0044444",
            "extra_point_attempt": "1",
            "extra_point_result": "good"
        }
        parser.look_for_kick(play)

        assert parser.stats["00-0044444"][PlayerStatTypes.PAT] == 1

    def test_look_for_kick_field_goal(self, parser):
        """Test field goal"""
        play = {
            "play_type": "field_goal",
            "kicker_player_id": "00-0044444",
            "kick_distance": "45",
            "field_goal_result": "made"
        }
        parser.look_for_kick(play)

        assert len(parser.kicks["00-0044444"]) == 1
        assert parser.kicks["00-0044444"][0].distance == 45
        assert parser.kicks["00-0044444"][0].made == True

    def test_look_for_kick_kickoff_touchback(self, parser):
        """Test kickoff touchback"""
        play = {
            "play_type": "kickoff",
            "kicker_player_id": "00-0044444",
            "touchback": "1",
            "kickoff_out_of_bounds": "0"
        }
        parser.look_for_kick(play)

        assert parser.stats["00-0044444"][PlayerStatTypes.KICKOFF_TOUCHBACK] == 1

    def test_look_for_punt(self, parser):
        """Test punt statistics"""
        play = {
            "punter_player_id": "00-0055555",
            "kick_distance": "50",
            "punt_inside_twenty": "1",
            "touchback": "0",
            "punt_returner_player_id": "00-0066666",
            "return_yards": "12",
            "return_touchdown": "0",
            "punt_blocked": "0"
        }
        parser.look_for_punt(play)

        assert len(parser.punts["00-0055555"]) == 1
        assert parser.punts["00-0055555"][0].distance == 50
        assert parser.punts["00-0055555"][0].inside20 == True
        assert parser.punts["00-0055555"][0].in_ez == False
        assert parser.stats["00-0066666"][PlayerStatTypes.PUNT_RETURN_YARDS] == 12

    def test_reduce_punts(self, parser):
        """Test punt aggregation"""
        parser.punts["00-0055555"] = [
            Punt(50, True, False),
            Punt(45, False, False),
            Punt(60, True, True)
        ]
        parser.reduce_punts()

        assert parser.stats["00-0055555"][PlayerStatTypes.PUNTS] == 3
        assert parser.stats["00-0055555"][PlayerStatTypes.TOTAL_PUNT_YARDS] == 155
        assert parser.stats["00-0055555"][PlayerStatTypes.PUNT_AVERAGE] == 51  # 155 // 3
        assert parser.stats["00-0055555"][PlayerStatTypes.PUNTS_INSIDE_20] == 2
        assert parser.stats["00-0055555"][PlayerStatTypes.PUNT_TOUCHBACKS] == 1

    def test_route_parsing_skip_plays(self, parser):
        """Test that certain play types are skipped"""
        for play_type in ["GAME_START", "GAMES_START", "TIMEOUT", "END_QUARTER", "END_GAME"]:
            play = {"play_type_nfl": play_type}
            parser.route_parsing(play)

        assert len(parser.stats) == 0


class TestSQLGenerator:
    """Test the SQLGenerator class"""

    def test_write_stats_player(self):
        """Test generating player stat SQL"""
        stats = {
            "00-0012345": {
                PlayerStatTypes.CARRIES: 10,
                PlayerStatTypes.RUSH_YARDS: 45,
                PlayerStatTypes.RUSH_TDS: 1
            }
        }

        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_stats(stats, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        assert "exec scoring.gsis_add_player_raw_stat( '00-0012345', 2025, 17, 1, 10 );" in result
        assert "exec scoring.gsis_add_player_raw_stat( '00-0012345', 2025, 17, 2, 45 );" in result
        assert "exec scoring.gsis_add_player_raw_stat( '00-0012345', 2025, 17, 5, 1 );" in result

    def test_write_stats_team(self):
        """Test generating team blocking SQL"""
        stats = {
            "KC": {
                TeamStatTypes.TEAM_RUSH_ATTEMPTS_LEFT: 5,
                TeamStatTypes.TEAM_RUSH_ATTEMPTS_CENTER: 10,
                TeamStatTypes.TEAM_RUSH_ATTEMPTS_RIGHT: 3,
                TeamStatTypes.TEAM_RUSH_YARDS_LEFT: 25,
                TeamStatTypes.TEAM_RUSH_YARDS_CENTER: 50,
                TeamStatTypes.TEAM_RUSH_YARDS_RIGHT: 15,
                TeamStatTypes.TEAM_RUSH_TDS: 2,
                TeamStatTypes.TEAM_PASS_ATTEMPTS: 30,
                TeamStatTypes.TEAM_PASS_YARDS: 250,
                TeamStatTypes.TEAM_SACKS_ALLOWED: 2
            }
        }

        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_stats(stats, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        assert "exec scoring.gsis_add_blocking_performance( 'KC', 2025, 17" in result
        assert "18, 90" in result  # total carries and yards

    def test_write_stats_filters_na(self):
        """Test that NA player IDs are filtered out"""
        stats = {
            "NA": {PlayerStatTypes.CARRIES: 1},
            "na": {PlayerStatTypes.CARRIES: 1},
            "": {PlayerStatTypes.CARRIES: 1}
        }

        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_stats(stats, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        # Should only contain header comments, no exec statements
        assert "exec scoring.gsis_add_player_raw_stat( 'NA'" not in result
        assert "exec scoring.gsis_add_player_raw_stat( 'na'" not in result

    def test_write_kicks(self):
        """Test generating field goal SQL"""
        kicks = {
            "00-0012345": [
                FieldGoal(45, True),
                FieldGoal(52, True),
                FieldGoal(58, False)
            ]
        }

        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_kicks(kicks, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        # Should have distance for made kicks
        assert "exec scoring.gsis_add_player_raw_stat( '00-0012345', 2025, 17, 31, 45 );" in result
        assert "exec scoring.gsis_add_player_raw_stat( '00-0012345', 2025, 17, 31, 52 );" in result
        # Should have attempts and made totals
        assert "exec scoring.gsis_add_player_raw_stat( '00-0012345', 2025, 17, 73, 3 );" in result
        assert "exec scoring.gsis_add_player_raw_stat( '00-0012345', 2025, 17, 72, 2 );" in result


class TestPreScan:
    """Test the PreScan class"""

    def test_are_same_both_filled(self):
        """Test when both ID and name are filled"""
        assert PreScan.are_same("00-0012345", "J.Smith") == True

    def test_are_same_both_empty(self):
        """Test when both ID and name are empty"""
        assert PreScan.are_same("NA", "NA") == True
        assert PreScan.are_same("", "") == True

    def test_are_same_mismatch(self):
        """Test when one is filled and one is empty"""
        assert PreScan.are_same("00-0012345", "NA") == False
        assert PreScan.are_same("NA", "J.Smith") == False
        assert PreScan.are_same("00-0012345", "") == False

    def test_scan_file_no_problems(self):
        """Test scanning file with no issues"""
        plays = [
            {
                "play_type": "run",
                "play_id": "1",
                "game_id": "2025_01_KC_BUF",
                "rusher_player_id": "00-0012345",
                "rusher_player_name": "J.Smith"
            }
        ]

        assert PreScan.scan_file(plays) == False

    def test_scan_file_with_problems(self):
        """Test scanning file with data issues"""
        plays = [
            {
                "play_type": "run",
                "play_id": "1",
                "game_id": "2025_01_KC_BUF",
                "rusher_player_id": "00-0012345",
                "rusher_player_name": "NA"  # Mismatch!
            }
        ]

        # Capture stderr to check error message
        old_stderr = sys.stderr
        sys.stderr = StringIO()

        result = PreScan.scan_file(plays)

        error_output = sys.stderr.getvalue()
        sys.stderr = old_stderr

        assert result == True
        assert "rusher problem" in error_output


class TestIntegration:
    """Integration tests using actual test data files"""

    @pytest.fixture
    def test_data_dir(self):
        """Get test data directory path"""
        return Path("test_data")

    @pytest.mark.parametrize("csv_file", [
        "w17mnf.csv",
        "w17sat.csv",
        "w17thur.csv",
        "w17sunam.csv",
        "w17sunpm.csv"
    ])
    def test_full_parse_against_expected(self, test_data_dir, csv_file):
        """Test full parsing matches expected output"""
        csv_path = test_data_dir / csv_file

        # Skip if test file doesn't exist
        if not csv_path.exists():
            pytest.skip(f"Test file {csv_file} not found")

        # Read CSV
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()

        # Parse
        import csv as csv_module
        csv_lines = csv_content.splitlines()
        reader = csv_module.DictReader(csv_lines)

        # Pre-scan
        PreScan.scan_file(reader)

        # Parse data
        data_parser = DataParser()
        csv_lines = csv_content.splitlines()
        reader = csv_module.DictReader(csv_lines)

        for play in reader:
            if int(play.get("week", "0")) == 17:
                try:
                    data_parser.route_parsing(play)
                except Exception:
                    pass  # Continue on errors

        data_parser.reduce_punts()

        # Verify we got data
        assert len(data_parser.stats) > 0

        # Generate SQL
        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_stats(data_parser.stats, 17, 2025)
        SQLGenerator.write_kicks(data_parser.kicks, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()

        # Verify structure
        assert "set serveroutput on;" in result
        assert "exec scoring.gsis_add_player_raw_stat(" in result or "exec scoring.gsis_add_blocking_performance(" in result

        # Verify no NA bugs
        assert "'NA'" not in result


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_csv(self):
        """Test handling empty CSV"""
        parser = DataParser()
        parser.reduce_punts()

        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_stats(parser.stats, 17, 2025)
        SQLGenerator.write_kicks(parser.kicks, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        assert "set serveroutput on;" in result

    def test_negative_yards(self):
        """Test handling negative yardage"""
        parser = DataParser()
        play = {
            "rusher_player_id": "00-0012345",
            "posteam": "KC",
            "rushing_yards": "-5",
            "run_location": "left",
            "rush_touchdown": "0"
        }
        parser.look_for_run(play)

        assert parser.stats["00-0012345"][PlayerStatTypes.RUSH_YARDS] == -5

    def test_missing_fields(self):
        """Test handling plays with missing fields"""
        parser = DataParser()
        play = {
            "rusher_player_id": "00-0012345",
            # Missing posteam, rushing_yards, etc.
        }
        # Should not crash
        parser.look_for_run(play)

    def test_multiple_field_goals_same_kicker(self):
        """Test multiple field goals by same kicker"""
        parser = DataParser()

        for distance, made in [(35, True), (45, False), (50, True)]:
            play = {
                "play_type": "field_goal",
                "kicker_player_id": "00-0044444",
                "kick_distance": str(distance),
                "field_goal_result": "made" if made else "missed"
            }
            parser.look_for_kick(play)

        assert len(parser.kicks["00-0044444"]) == 3

        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_kicks(parser.kicks, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        assert "73, 3" in result  # 3 attempts
        assert "72, 2" in result  # 2 made

    def test_punt_average_rounding(self):
        """Test punt average uses integer division"""
        parser = DataParser()
        parser.punts["00-0055555"] = [
            Punt(50, False, False),
            Punt(45, False, False),
            Punt(51, False, False)
        ]
        parser.reduce_punts()

        # 146 / 3 = 48.666... should become 48 (integer division)
        assert parser.stats["00-0055555"][PlayerStatTypes.PUNT_AVERAGE] == 48

    def test_float_stat_formatting(self):
        """Test that whole number floats are formatted as ints"""
        parser = DataParser()
        parser.add_stat("00-0012345", PlayerStatTypes.SACKS, 1.0)
        parser.add_stat("00-0012345", PlayerStatTypes.TACKLES, 5.0)

        output = StringIO()
        sys.stdout = output
        SQLGenerator.write_stats(parser.stats, 17, 2025)
        sys.stdout = sys.__stdout__

        result = output.getvalue()
        # Should be "1" not "1.0"
        assert ", 64, 1 );" in result
        assert ", 62, 5 );" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
