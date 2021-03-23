Nascent software for EEG/EMG or whatever else G collection.

Now only has basic support for OpenBCI Cyton board.

## Notes

SD file sizes are baselined for 8 channel on 250hz sample rate, apply following formula to estimate required size: `<necessary time>*(<number of channels>/8)*(<sampling rate>/250)`
