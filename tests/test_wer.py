from eval.wer import resolve_audio_path, wer


def test_word_error_rate():
    assert wer("The cat sat", "the cat sat") == 0
    assert wer("the cat sat", "the cat") == 1 / 3


def test_resolves_clip_paths_relative_to_csv(tmp_path):
    (tmp_path / "clips").mkdir()
    clip = tmp_path / "clips" / "sample.wav"
    clip.write_bytes(b"audio")
    csv_path = tmp_path / "phrases.csv"
    assert resolve_audio_path("clips/sample.wav", csv_path) == clip.resolve()
