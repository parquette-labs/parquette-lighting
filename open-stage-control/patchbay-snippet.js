set('output_patchbay/chan_1', []);
set('output_patchbay/chan_2', []);
set('output_patchbay/chan_3', []);
set('output_patchbay/chan_4', []);
set('output_patchbay/chan_5', []);
set('output_patchbay/chan_6', []);
set('output_patchbay/chan_7', []);
set('output_patchbay/chan_8', []);
set('output_patchbay/chan_9', []);
set('output_patchbay/chan_10', []);
set('output_patchbay/chan_spot', []);
switch(get(id)) {
  case "MONO": {
    set('output_patchbay/chan_1', [
      "left_1",
      "left_2",
      "left_3",
      "left_4",
      "right_1",
      "right_2",
      "right_3",
      "right_4",
      "front_1",
      "front_2",
      "spot"
    ])
    set('output_patchbay/chan_spot', ['spot']);
    break;
  }
  case "HEX": {
    set('output_patchbay/chan_1', [
      "front_1",
      "front_2",
    ])
    set('output_patchbay/chan_2', [
      "left_1",
      "right_1",
    ])
    set('output_patchbay/chan_3', [
      "left_2",
      "right_2",
    ])
    set('output_patchbay/chan_4', [
      "left_3",
      "right_3",
    ])
    set('output_patchbay/chan_5', [
      "left_4",
      "right_4",
    ])
    set('output_patchbay/chan_spot', ['spot']);
    break;
  }
  case "DECA": {
    set('output_patchbay/chan_spot', ['spot']);
    break;
  }
  case "FWD": {
    set('output_patchbay/chan_spot', ['spot']);
    break;
  }
  case "BACK": {
    set('output_patchbay/chan_spot', ['spot']);
    break;
  }
  case "ZIG": {
    set('output_patchbay/chan_spot', ['spot']);
    break;
  }
}