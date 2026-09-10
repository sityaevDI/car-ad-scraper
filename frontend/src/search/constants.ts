// Canonical values normalized by app/sources/polovniautomobili/mapper.py — kept in sync manually,
// there's no backend endpoint enumerating them (only /vehicles/makes for make/model).
export const FUEL_TYPE_OPTIONS = [
  { value: 'petrol', label: 'Бензин' },
  { value: 'diesel', label: 'Дизель' },
  { value: 'hybrid', label: 'Гибрид' },
  { value: 'electric', label: 'Электро' },
  { value: 'lpg', label: 'Газ (LPG)' },
  { value: 'cng', label: 'Газ (CNG)' },
] as const

export const TRANSMISSION_OPTIONS = [
  { value: 'manual', label: 'Механика' },
  { value: 'automatic', label: 'Автомат' },
] as const

export const BODY_TYPE_OPTIONS = [
  { value: 'sedan', label: 'Седан' },
  { value: 'wagon', label: 'Универсал' },
  { value: 'hatchback', label: 'Хэтчбек' },
  { value: 'suv', label: 'Внедорожник' },
  { value: 'coupe', label: 'Купе' },
  { value: 'convertible', label: 'Кабриолет' },
  { value: 'pickup', label: 'Пикап' },
  { value: 'minivan', label: 'Минивэн' },
] as const

// Canonical values normalized by app/sources/polovniautomobili/mapper.py's
// _EQUIPMENT_NORMALIZED — kept in sync manually, same as the option lists above.
export const EQUIPMENT_POPULAR = [
  { value: 'apple_carplay', label: 'Apple CarPlay' },
  { value: 'android_auto', label: 'Android Auto' },
  { value: 'adaptive_cruise_control', label: 'Адаптивный круиз-контроль' },
  { value: 'navigation_system', label: 'Навигация' },
  { value: 'panoramic_roof', label: 'Панорамная крыша' },
  { value: 'heated_seats', label: 'Подогрев сидений' },
  { value: 'parking_sensors', label: 'Парктроник' },
  { value: 'camera', label: 'Камера' },
  { value: 'alloy_wheels', label: 'Легкосплавные диски' },
  { value: 'keyless_start', label: 'Запуск без ключа' },
] as const

interface EquipmentOption {
  value: string
  label: string
}

export const EQUIPMENT_CATEGORIES: { category: string; options: EquipmentOption[] }[] = [
  {
    category: 'Мультимедиа и связь',
    options: [
      { value: 'navigation_system', label: 'Навигация' },
      { value: 'bluetooth', label: 'Bluetooth' },
      { value: 'apple_carplay', label: 'Apple CarPlay' },
      { value: 'android_auto', label: 'Android Auto' },
      { value: 'touchscreen', label: 'Сенсорный экран' },
      { value: 'multimedia_system', label: 'Мультимедиа-система' },
      { value: 'digital_instrument_cluster', label: 'Цифровая приборная панель' },
      { value: 'head_up_display', label: 'Проекционный дисплей (Head-up)' },
      { value: 'voice_control', label: 'Голосовое управление' },
      { value: 'hands_free', label: 'Hands-free' },
      { value: 'usb', label: 'USB' },
      { value: 'aux_input', label: 'AUX-разъём' },
      { value: 'power_outlet_12v', label: 'Розетка 12V' },
      { value: 'hard_disk', label: 'Жёсткий диск' },
      { value: 'subwoofer', label: 'Сабвуфер' },
      { value: 'mp3', label: 'MP3' },
      { value: 'digital_radio', label: 'Цифровое радио' },
      { value: 'radio_cassette', label: 'Радио/Магнитола' },
      { value: 'radio_cd', label: 'Радио CD' },
      { value: 'cd_changer', label: 'CD-чейнджер' },
      { value: 'dvd_tv', label: 'DVD/TV' },
    ],
  },
  {
    category: 'Безопасность и ассистенты',
    options: [
      { value: 'cruise_control', label: 'Круиз-контроль' },
      { value: 'adaptive_cruise_control', label: 'Адаптивный круиз-контроль' },
      { value: 'automatic_parking', label: 'Автопарковка' },
      { value: 'parking_sensors', label: 'Парктроник' },
      { value: 'camera', label: 'Камера' },
      { value: 'camera_360', label: 'Камера 360°' },
      { value: 'front_night_vision_camera', label: 'Камера ночного видения' },
      { value: 'mirror_tilt_in_reverse', label: 'Зеркало наклоняется при заднем ходе' },
      { value: 'start_stop_system', label: 'Старт-стоп' },
      { value: 'hill_start_assist', label: 'Помощь при старте на подъёме' },
      { value: 'tire_pressure_monitor', label: 'Контроль давления в шинах' },
      { value: 'electronic_parking_brake', label: 'Электронный ручник' },
      { value: 'ceramic_brakes', label: 'Керамические тормоза' },
      { value: 'isofix', label: 'ISOFIX' },
      { value: 'factory_child_seat', label: 'Заводское детское кресло' },
      { value: 'drive_mode_selector', label: 'Режимы движения' },
      { value: 'autonomous_driving', label: 'Автономное вождение' },
    ],
  },
  {
    category: 'Комфорт и удобство',
    options: [
      { value: 'power_steering', label: 'Гидроусилитель руля' },
      { value: 'multifunction_steering_wheel', label: 'Мультифункциональный руль' },
      { value: 'remote_central_locking', label: 'Дистанционный центральный замок' },
      { value: 'keyless_start', label: 'Запуск без ключа' },
      { value: 'trip_computer', label: 'Бортовой компьютер' },
      { value: 'power_windows', label: 'Электростеклоподъёмники' },
      { value: 'power_mirrors', label: 'Электрозеркала' },
      { value: 'heated_mirrors', label: 'Подогрев зеркал' },
      { value: 'power_folding_mirrors', label: 'Складывающиеся электрозеркала' },
      { value: 'auto_dimming_mirror', label: 'Автозатемнение зеркала' },
      { value: 'soft_close_doors', label: 'Доводчики дверей' },
      { value: 'power_trunk_opening', label: 'Электрооткрывание багажника' },
      { value: 'power_trunk_closing', label: 'Электрозакрывание багажника' },
      { value: 'wireless_phone_charging', label: 'Беспроводная зарядка телефона' },
      { value: 'ambient_lighting', label: 'Атмосферная подсветка' },
      { value: 'cup_holders', label: 'Подстаканники' },
      { value: 'cooled_glovebox', label: 'Охлаждаемый бардачок' },
      { value: 'armrest', label: 'Подлокотник' },
      { value: 'rain_sensor', label: 'Датчик дождя' },
      { value: 'light_sensor', label: 'Датчик света' },
      { value: 'heated_windshield', label: 'Подогрев лобового стекла' },
      { value: 'auxiliary_heater', label: 'Автономный отопитель (Webasto)' },
    ],
  },
  {
    category: 'Сиденья и салон',
    options: [
      { value: 'height_adjustable_seats', label: 'Регулировка сидений по высоте' },
      { value: 'power_adjustable_seats', label: 'Электрорегулировка сидений' },
      { value: 'heated_seats', label: 'Подогрев сидений' },
      { value: 'ventilated_seats', label: 'Вентиляция сидений' },
      { value: 'massage_seats', label: 'Массаж сидений' },
      { value: 'seat_memory', label: 'Память положения сидений' },
      { value: 'sport_seats', label: 'Спортивные сиденья' },
      { value: 'rear_window_curtains', label: 'Шторки на задние стёкла' },
    ],
  },
  {
    category: 'Освещение',
    options: [
      { value: 'fog_lights', label: 'Противотуманные фары' },
      { value: 'xenon_headlights', label: 'Ксеноновые фары' },
      { value: 'led_headlights', label: 'LED фары (передние)' },
      { value: 'led_taillights', label: 'LED фонари (задние)' },
      { value: 'adaptive_headlights', label: 'Адаптивные фары' },
      { value: 'matrix_headlights', label: 'Матричные фары' },
      { value: 'daytime_running_lights', label: 'Дневные ходовые огни' },
      { value: 'headlight_washers', label: 'Омыватели фар' },
    ],
  },
  {
    category: 'Экстерьер',
    options: [
      { value: 'metallic_paint', label: 'Металлик' },
      { value: 'body_colored_bumpers', label: 'Бамперы в цвет кузова' },
      { value: 'sunroof', label: 'Люк' },
      { value: 'panoramic_roof', label: 'Панорамная крыша' },
      { value: 'tinted_windows', label: 'Тонированные стёкла' },
      { value: 'roof_rack', label: 'Багажник на крышу' },
      { value: 'tow_hook', label: 'Фаркоп' },
      { value: 'alloy_wheels', label: 'Легкосплавные диски' },
      { value: 'spare_wheel', label: 'Запасное колесо' },
      { value: 'ski_bag', label: 'Лыжный багажник (шторка)' },
      { value: 'ski_hatch', label: 'Лючок для лыж' },
    ],
  },
  {
    category: 'Руль',
    options: [
      { value: 'leather_steering_wheel', label: 'Кожаный руль' },
      { value: 'wood_leather_steering_wheel', label: 'Руль дерево/кожа' },
      { value: 'steering_wheel_height_adjustment', label: 'Регулировка руля по высоте' },
      { value: 'heated_steering_wheel', label: 'Подогрев руля' },
      { value: 'paddle_shifters', label: 'Подрулевые лепестки' },
    ],
  },
  {
    category: 'Ходовая часть',
    options: [
      { value: 'air_suspension', label: 'Пневмоподвеска' },
      { value: 'sport_suspension', label: 'Спортивная подвеска' },
      { value: 'four_wheel_steering', label: 'Полноуправляемое шасси (4 колеса)' },
      { value: 'differential_lock', label: 'Блокировка дифференциала' },
      { value: 'dpf_filter', label: 'Сажевый фильтр (DPF)' },
    ],
  },
]

export const PAGE_SIZE = 20
export const DRILL_DOWN_PAGE_SIZE = 10
