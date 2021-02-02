import os
import pydub
import pydub_mixer
import pynbs
import math
from collections import namedtuple
import time
import zipfile


SOUNDS_PATH = "sounds"

Note = namedtuple('Note', 'tick layer instrument pitch volume panning')



default_instruments = [
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
	return pydub.AudioSegment.from_file(path)


def load_instruments(song, path):
	segments = []
	
	for ins in default_instruments:
		filename = os.path.join(os.getcwd(), SOUNDS_PATH, ins)
		sound = load_sound(filename)
		segments.append(sound)
		
	for ins in song.instruments:
		print(ins)
		if os.path.splitext(path)[1] == '.zip':
			zip_file = zipfile.ZipFile(path, 'r')
			file = zip_file.read(ins.file)
		else:
			file = os.path.join(path, ins.file)
		sound = load_sound(file)
		segments.append(sound)
	
	return segments
	
	
def sync(sound, channels=2, frame_rate=44100, sample_width=2):
	return sound.set_channels(channels).set_frame_rate(frame_rate).set_sample_width(sample_width)


def change_speed(sound, speed=1.0):
	# From: https://stackoverflow.com/a/51434954/9045426
	
	new = sound._spawn(sound.raw_data, overrides={
								"frame_rate": int(sound.frame_rate * speed)
							})
	
	return new.set_frame_rate(sound.frame_rate)


def get_pitch(note):
	key = note.key - 45
	detune = note.pitch / 100
	pitch = key + detune
	return pitch


def get_volume(note, layer):
	layer_vol = layer.volume / 100
	note_vol = note.velocity / 100
	vol = layer_vol * note_vol
	return vol


def get_panning(note, layer):
	layer_pan = layer.panning / 100
	note_pan = note.panning / 100
	if layer_pan == 0:
		pan = note_pan
	else:
		pan = (layer_pan + note_pan) / 2
	return pan


def key_to_pitch(key):
	return 2**((key) / 12)


def vol_to_gain(vol):
	return math.log(max(vol, 0.0001), 10) * 20


def sort_notes(song):

	notes = []
	for note in song.notes:
		layer = song.layers[note.layer]
		
		pitch = get_pitch(note)
		volume = get_volume(note, layer)
		panning = get_panning(note, layer)
		
		new = Note(note.tick, note.layer, note.instrument, pitch, volume, panning)
		notes.append(new)
	
	return sorted(notes, key=lambda x: (x.pitch, x.instrument, x.volume, x.panning))
	

def render_audio(song, output_path, custom_sound_path=SOUNDS_PATH, loops=0, fadeout=False, target_bitrate=320, target_size=None):
	
	start = time.time()
	
	instruments = load_instruments(song, custom_sound_path)
	
	length = song.header.song_length / song.header.tempo * 1000
	track = pydub.AudioSegment.silent(duration=length)
	master_gain = -12.0
	mixer = pydub_mixer.Mixer()
	
	last_ins = None
	last_key = None
	last_vol = None
	last_pan = None
	
	ins_changes = 0
	key_changes = 0
	vol_changes = 0
	pan_changes = 0
	
	sorted_notes = sort_notes(song)
	for i, note in enumerate(sorted_notes):
		
		ins = note.instrument
		key = note.pitch
		vol = note.volume
		pan = note.panning
		
		#Todo: optimize and avoid gain/pitch/key calculation if default value!
		#Todo: ignore locked layers
		#Todo: pan has a loudness compensation? https://github.com/jiaaro/pydub/blob/master/API.markdown#audiosegmentpan
		
		if ins != last_ins:
			last_key = None
			last_vol = None
			last_pan = None
			sound1 = instruments[note.instrument]
			sound1 = sync(sound1.apply_gain(master_gain))
			ins_changes += 1
			
		if key != last_key:
			last_vol = None
			last_pan = None
			pitch = key_to_pitch(key)
			sound2 = change_speed(sound1, pitch)
			key_changes += 1
			
		if vol != last_vol:
			last_pan = None
			gain = vol_to_gain(vol)
			sound3 = sound2.apply_gain(gain)
			vol_changes += 1
			
		if pan != last_pan:
			sound4 = sound3.pan(pan)
			sound = sound4
			pan_changes += 1
		
		last_ins = ins
		last_key = key
		last_vol = vol
		last_pan = pan
		
		if i % 10 == 0:
			print("Converting note {}/{} (tick: {}, layer: {}, vol: {}, pan: {}, pit: {})".format(i+1, len(song.notes), note.tick, note.layer, vol, pan, pitch))
		
		pos = note.tick / song.header.tempo * 1000
		
		mixer.overlay(sound, position=pos)
	
	track = mixer.to_audio_segment()
	
	# Normalize to -3 dBFS
	track = track.normalize(headroom=0.0)
	
	seconds = track.duration_seconds
	
	if target_size:
		bitrate = (target_size / seconds) * 8
		bitrate = min(bitrate, target_bitrate)
	else:
		bitrate = target_bitrate
	
	outfile = track.export(output_path,
							   format="mp3",
							   bitrate="{}k".format(bitrate),
							   tags={"artist": "test"})
	
	outfile.close()
	
	end = time.time()
	
	with open("tests/log_{}.txt".format(os.path.basename(output_path)), 'w') as f:
		f.write("Ins: {}\nKey: {}\nVol: {}\nPan: {}\n\nStart: {}\nEnd: {}\nTime elapsed: {}".format(ins_changes, key_changes, vol_changes, pan_changes, start, end, end-start))
		
	
