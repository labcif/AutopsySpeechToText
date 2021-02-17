# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['inaSpeechSegmenter/scripts/ina_speech_segmenter.py'],
             pathex=['/home/miguel/Development/IPL/investigacao/speech_to_text_dev/autopsy_speech_modules/python'],
             binaries=[],
             datas=[('inaSpeechSegmenter/inaSpeechSegmenter/keras_male_female_cnn.hdf5', 'inaSpeechSegmenter'), ('inaSpeechSegmenter/inaSpeechSegmenter/keras_speech_music_noise_cnn.hdf5', 'inaSpeechSegmenter')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='ina_speech_segmenter',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='ina_speech_segmenter')
