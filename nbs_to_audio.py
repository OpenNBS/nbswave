import os
import pydub
import pynbs


SOUNDS_PATH = "sounds"


instruments = [
	"harp.ogg",
	"dbass.ogg",
	"bdrum.ogg",
	"sdrum.ogg",
	"click.ogg",
	"guitar.ogg",
	"flute.ogg",
	"bell.ogg",
	"icechime.ogg",
	"xylobone.ogg",
	"iron_xylophone.ogg",
	"cow_bell.ogg",
	"didgeridoo.ogg",
	"bit.ogg",
	"banjo.ogg",
	"pling.ogg"
]


def load_sound(path):
	return pydub.AudioSegment.from_file(path, format='ogg')


def load_instruments():
	segments = []
	for ins in instruments:
		filename = os.path.join(os.getcwd(), SOUNDS_PATH, ins)
		sound = load_sound(filename)
		segments.append(sound)

	return segments


def change_speed(sound, speed=1.0):
	# From: https://stackoverflow.com/a/51434954/9045426
	
	new = sound._spawn(sound.raw_data, overrides={
								"frame_rate": int(sound.frame_rate * speed)
							})
	
	return new.set_frame_rate(sound.frame_rate)


def render_audio(song, output_path, loops=0, fadeout=False, target_bitrate=320, target_size=None):
	
	instruments = load_instruments()
	
	length = song.header.song_length / song.header.tempo * 1000
	track = pydub.AudioSegment.silent(duration=length)
	master_gain = -12.0
	
	for i, note in enumerate(song.notes):
		
		if note.instrument > song.header.default_instruments - 1:
			continue
		
		sound = instruments[note.instrument]
		
		pitch = 2**((note.key - 45) / 12)
		pos = note.tick / song.header.tempo * 1000
		
		layer_vol = song.layers[note.layer].volume / 100
		note_vol = note.velocity / 100
		vol = layer_vol * note_vol
		gain = -((1.0 - vol) * 30)
		
		layer_pan = song.layers[note.layer].panning / 100
		note_pan = note.panning / 100
		pan = -(layer_pan + note_pan) / 2
		
		print("Converting note {}/{} (tick: {}, vol: {}, pan: {}, pit: {})".format(i+1, len(song.notes), note.tick, vol, pan, pitch))
		
		sound = sound.apply_gain(gain).pan(pan)
		sound = sound.apply_gain(master_gain)
		sound = change_speed(sound, pitch)
		
		# Ensure track is long enough to hold the note
		diff = (pos + len(sound)) - len(track)
		if diff > 0:
			track = track + pydub.AudioSegment.silent(duration=diff)
		
		track = track.overlay(sound, position=pos)
	
	# Normalize to -3 dBFS
	track = track.normalize(headroom=0.0)
	
	seconds = track.duration_seconds
	
	if target_size:
		bitrate = (target_size / seconds) * 8
		bitrate = min(bitrate, target_bitrate)
	else:
		bitrate = target_bitrate
	
	file_handle = track.export(output_path,
							   format="mp3",
							   bitrate="{}k".format(bitrate),
							   tags={"artist": "test"})
						   
	return file_handle
