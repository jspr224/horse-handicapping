-- tracks
CREATE TABLE IF NOT EXISTS tracks (
	track_id serial PRIMARY KEY 
	, track_code varchar(10) UNIQUE NOT NULL 
	, track_name varchar(100) NOT NULL 
	, location varchar(100)
	, primary_surface varchar(20)
)
;

-- seed the two tracks 
INSERT INTO tracks (track_code, track_name, location, primary_surface)
VALUES 
	('KEE', 'Keeneland', 'Lexington, KY', 'Dirt/Turf')
	, ('CD', 'Churchill Downs', 'Louisville, KY', 'Dirt/Turf')
ON conflict (track_code) do nothing
;

-- Horses
CREATE TABLE IF NOT EXISTS horses(
	horse_id serial PRIMARY KEY 
	, horse_name varchar(100) NOT NULL
	, color varchar(30)
	, sex varchar(10)
	, sire varchar(100)
	, dam varchar(100)
	, breeder varchar(100)
	, foal_date date
	, state_bred varchar(50)
	, unique(horse_name, foal_date)
)
;

-- Trainers
CREATE TABLE IF NOT EXISTS trainers (
	trainer_id serial PRIMARY KEY 
	, trainer_name varchar(100) UNIQUE NOT NULL
	, meet_win_pct decimal(5, 2)
	, meet_roi decimal(6, 2)
	, meet_starts integer
)
;

-- Jockeys
CREATE TABLE IF NOT EXISTS jockeys (
	jockey_id serial PRIMARY KEY 
	, jockey_name varchar(100) UNIQUE NOT NULL 
	, meet_win_pct decimal(5, 2)
	, meet_roi decimal(6, 2)
	, meet_starts integer 
)
;

-- race cards 
CREATE TABLE IF NOT EXISTS race_cards (
	card_id serial PRIMARY KEY 
	, track_id integer REFERENCES tracks(track_id)
	, race_date date NOT NULL 
	, weather varchar(50)
	, condition_dirt varchar(50)
	, condition_turf varchar(50)
	, pp_source varchar(50) DEFAULT 'BrisNet'
	, unique(track_id, race_date)
)
;

-- races 
CREATE TABLE IF NOT EXISTS races (
	race_id serial PRIMARY KEY 
	, card_id integer REFERENCES race_cards(card_id)
	, race_number integer NOT NULL
	, distance varchar(30)
	, surface varchar(20)
	, race_type varchar(50)
	, claiming_price integer
	, purse integer 
	, conditions text 
	, pace_par_e1 decimal(6, 2)
	, pace_par_e2 decimal(6, 2)
	, pace_par_late decimal(6, 2)
	, speed_par decimal(6, 2)
	, unique(card_id, race_number)
)
;

-- entries
CREATE TABLE IF NOT EXISTS entries (
	entry_id serial PRIMARY KEY 
	, race_id integer REFERENCES races(race_id)
	, horse_id integer REFERENCES horses(horse_id)
	, trainer_id integer REFERENCES trainers(trainer_id)
	, jockey_id integer REFERENCES jockeys(jockey_id)
	, post_position integer
	, running_style varchar(5)
	, morning_line decimal(8, 2)
	, actual_odds decimal(8, 2)
	, weight integer
	, equipment varchar(20)
	, prime_power decimal(7, 2)
	, speed_last_race decimal(6, 2)
	, back_speed decimal(6, 2)
	, avg_class_last3 decimal(7, 2)
	, e1_pace decimal(6, 2)
	, e2_pace decimal(6, 2)
	, late_pace decimal(6, 2)
	, best_beyer_at_dist integer
	, days_since_last_race integer
	, trainer_angle_notes text
	, meet_trainer_win_pct decimal(5, 2)
	, meet_jockey_win_pct decimal(5, 2)
	, trainer_jockey_win_pct decimal(5, 2)
)
;

-- past performances
CREATE TABLE IF NOT EXISTS past_performances (
	pp_id serial PRIMARY KEY 
	, entry_id integer REFERENCES entries(entry_id)
	, sequence_num integer NOT NULL
	, race_date date
	, track varchar(10)
	, distance varchar(30)
	, surface varchar(20)
	, race_type varchar(50)
	, claiming_price integer
	, e1_pace decimal(6, 2)
	, e2_pace decimal(6, 2)
	, late_pace decimal(6, 2)
	, beyer_figure integer
	, first_call_pos integer
	, second_call_pos integer
	, finish_pos integer
	, final_odds decimal(8, 2)
	, comment text 
)
;

-- track bias 
CREATE TABLE IF NOT EXISTS track_bias (
	bias_id serial PRIMARY KEY 
	, race_id integer REFERENCES races(race_id)
	, scope varchar(20)
	, surface varchar(20)
	, distance_category varchar(20)
	, e_impact decimal(5, 2)
	, ep_impact decimal(5, 2)
	, p_impact decimal(5, 2)
	, s_impact decimal(5, 2)
	, rail_impact decimal(5, 2)
	, posts_1_3_impact decimal(5, 2)
	, posts_4_7_impact decimal(5, 2)
	, posts_8plus_impact decimal(5, 2)
	, wire_pct decimal(5, 2)
	, confirmed_bias varchar(50)
)
;

-- results
CREATE TABLE IF NOT EXISTS results (
	result_id serial PRIMARY KEY
	, entry_id integer REFERENCES entries(entry_id) UNIQUE
	, finish_position integer
	, actual_odds decimal(8, 2)
	, beyer_earned integer
	, lengths_behind decimal(6, 2)
	, pace_position_1c varchar(10)
	, pace_position_2c varchar(10)
	, stretch_position varchar(10)
	, footnote_comment text
	, claimed boolean DEFAULT FALSE
	, claimed_price integer
)
;

-- analysis
CREATE TABLE IF NOT EXISTS my_analysis (
	analysis_id serial PRIMARY KEY
	, entry_id integer REFERENCES entries(entry_id) UNIQUE
	, pillar_speed_score integer
	, pillar_class_score integer
	, pillar_pace_score integer
	, pillar_connections_score integer
	, bias_adjustment integer
	, total_score integer
	, tier_rating varchar(5)
	, bet_type varchar(20)
	, stake decimal(8, 2)
	, returned decimal(8, 2)
	, notes text
)
;

	