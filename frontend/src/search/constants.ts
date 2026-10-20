// Canonical values normalized by app/sources/polovniautomobili/mapper.py — kept in sync manually,
// there's no backend endpoint enumerating them (only /vehicles/makes for make/model).
// Display labels live in the i18n dictionaries: options.<group>.<value>, equipment.<value>,
// equipmentCategory.<category> (see optionLabel / equipmentLabel in ../i18n).
export const FUEL_TYPE_OPTIONS = [
  { value: 'petrol' },
  { value: 'diesel' },
  { value: 'hybrid' },
  { value: 'hybrid_petrol' },
  { value: 'hybrid_diesel' },
  { value: 'plugin_hybrid' },
  { value: 'electric' },
  { value: 'lpg' },
  { value: 'cng' },
] as const

export const TRANSMISSION_OPTIONS = [
  { value: 'manual' },
  { value: 'automatic' },
] as const

export const BODY_TYPE_OPTIONS = [
  { value: 'sedan' },
  { value: 'wagon' },
  { value: 'hatchback' },
  { value: 'suv' },
  { value: 'coupe' },
  { value: 'convertible' },
  { value: 'pickup' },
  { value: 'minivan' },
] as const

// Canonical values normalized by app/sources/polovniautomobili/mapper.py's
// _INTERIOR_MATERIAL_NORMALIZED — kept in sync manually, same as the option lists above. Only
// populated from a listing's detail page (see that mapper's docstring), so filtering by this
// excludes listings whose detail page hasn't been fetched/re-fetched yet.
export const INTERIOR_MATERIAL_OPTIONS = [
  { value: 'cloth' },
  { value: 'leather' },
  { value: 'combined_leather' },
  { value: 'velour' },
  { value: 'other' },
] as const

// Canonical values normalized by app/sources/polovniautomobili/mapper.py's
// _AIR_CONDITION_NORMALIZED — kept in sync manually, same as the option lists above. Only
// populated from a listing's detail page (see that mapper's docstring), so filtering by this
// excludes listings whose detail page hasn't been fetched/re-fetched yet.
export const AIR_CONDITION_OPTIONS = [
  { value: 'none' },
  { value: 'manual' },
  { value: 'automatic' },
] as const

// Canonical values normalized by app/sources/polovniautomobili/mapper.py's
// _DRIVE_TYPE_NORMALIZED — kept in sync manually, same as the option lists above. Only populated
// from a listing's detail page (see that mapper's docstring), so filtering by this excludes
// listings whose detail page hasn't been fetched/re-fetched yet.
export const DRIVE_TYPE_OPTIONS = [
  { value: 'front' },
  { value: 'rear' },
  { value: 'awd' },
  { value: 'awd_low_range' },
] as const

// Canonical values are the raw seat count as a string (see mapper.py's normalize_seats) — kept
// in sync manually with the site's own "seats" facet (2-9).
export const SEATS_OPTIONS = [
  { value: '2' },
  { value: '3' },
  { value: '4' },
  { value: '5' },
  { value: '6' },
  { value: '7' },
  { value: '8' },
  { value: '9' },
] as const

// Canonical values normalized by app/sources/polovniautomobili/mapper.py's
// _EQUIPMENT_NORMALIZED — kept in sync manually, same as the option lists above.
export const EQUIPMENT_POPULAR = [
  { value: 'apple_carplay' },
  { value: 'android_auto' },
  { value: 'adaptive_cruise_control' },
  { value: 'navigation_system' },
  { value: 'panoramic_roof' },
  { value: 'heated_seats' },
  { value: 'parking_sensors' },
  { value: 'camera' },
  { value: 'alloy_wheels' },
  { value: 'keyless_start' },
] as const

interface EquipmentOption {
  value: string
}

export const EQUIPMENT_CATEGORIES: { category: string; options: EquipmentOption[] }[] = [
  {
    category: 'multimedia',
    options: [
      { value: 'navigation_system' },
      { value: 'bluetooth' },
      { value: 'apple_carplay' },
      { value: 'android_auto' },
      { value: 'touchscreen' },
      { value: 'multimedia_system' },
      { value: 'digital_instrument_cluster' },
      { value: 'head_up_display' },
      { value: 'voice_control' },
      { value: 'hands_free' },
      { value: 'usb' },
      { value: 'aux_input' },
      { value: 'power_outlet_12v' },
      { value: 'hard_disk' },
      { value: 'subwoofer' },
      { value: 'mp3' },
      { value: 'digital_radio' },
      { value: 'radio_cassette' },
      { value: 'radio_cd' },
      { value: 'cd_changer' },
      { value: 'dvd_tv' },
    ],
  },
  {
    category: 'safety',
    options: [
      { value: 'cruise_control' },
      { value: 'adaptive_cruise_control' },
      { value: 'automatic_parking' },
      { value: 'parking_sensors' },
      { value: 'camera' },
      { value: 'camera_360' },
      { value: 'front_night_vision_camera' },
      { value: 'mirror_tilt_in_reverse' },
      { value: 'start_stop_system' },
      { value: 'hill_start_assist' },
      { value: 'tire_pressure_monitor' },
      { value: 'electronic_parking_brake' },
      { value: 'ceramic_brakes' },
      { value: 'isofix' },
      { value: 'factory_child_seat' },
      { value: 'drive_mode_selector' },
      { value: 'autonomous_driving' },
    ],
  },
  {
    category: 'comfort',
    options: [
      { value: 'power_steering' },
      { value: 'multifunction_steering_wheel' },
      { value: 'remote_central_locking' },
      { value: 'keyless_start' },
      { value: 'trip_computer' },
      { value: 'power_windows' },
      { value: 'power_mirrors' },
      { value: 'heated_mirrors' },
      { value: 'power_folding_mirrors' },
      { value: 'auto_dimming_mirror' },
      { value: 'soft_close_doors' },
      { value: 'power_trunk_opening' },
      { value: 'power_trunk_closing' },
      { value: 'wireless_phone_charging' },
      { value: 'ambient_lighting' },
      { value: 'cup_holders' },
      { value: 'cooled_glovebox' },
      { value: 'armrest' },
      { value: 'rain_sensor' },
      { value: 'light_sensor' },
      { value: 'heated_windshield' },
      { value: 'auxiliary_heater' },
    ],
  },
  {
    category: 'seats',
    options: [
      { value: 'height_adjustable_seats' },
      { value: 'power_adjustable_seats' },
      { value: 'heated_seats' },
      { value: 'ventilated_seats' },
      { value: 'massage_seats' },
      { value: 'seat_memory' },
      { value: 'sport_seats' },
      { value: 'rear_window_curtains' },
    ],
  },
  {
    category: 'lighting',
    options: [
      { value: 'fog_lights' },
      { value: 'xenon_headlights' },
      { value: 'led_headlights' },
      { value: 'led_taillights' },
      { value: 'adaptive_headlights' },
      { value: 'matrix_headlights' },
      { value: 'daytime_running_lights' },
      { value: 'headlight_washers' },
    ],
  },
  {
    category: 'exterior',
    options: [
      { value: 'metallic_paint' },
      { value: 'body_colored_bumpers' },
      { value: 'sunroof' },
      { value: 'panoramic_roof' },
      { value: 'tinted_windows' },
      { value: 'roof_rack' },
      { value: 'tow_hook' },
      { value: 'alloy_wheels' },
      { value: 'spare_wheel' },
      { value: 'ski_bag' },
      { value: 'ski_hatch' },
    ],
  },
  {
    category: 'steeringWheel',
    options: [
      { value: 'leather_steering_wheel' },
      { value: 'wood_leather_steering_wheel' },
      { value: 'steering_wheel_height_adjustment' },
      { value: 'heated_steering_wheel' },
      { value: 'paddle_shifters' },
    ],
  },
  {
    category: 'chassis',
    options: [
      { value: 'air_suspension' },
      { value: 'sport_suspension' },
      { value: 'four_wheel_steering' },
      { value: 'differential_lock' },
      { value: 'dpf_filter' },
    ],
  },
]

export const PAGE_SIZE = 20
export const DRILL_DOWN_PAGE_SIZE = 10
