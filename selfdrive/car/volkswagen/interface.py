from cereal import car
from panda import Panda
from common.conversions import Conversions as CV
from selfdrive.car import STD_CARGO_KG, get_safety_config, create_mads_event
from selfdrive.car.interfaces import CarInterfaceBase
from selfdrive.car.volkswagen.values import CAR, PQ_CARS, CANBUS, NetworkLocation, TransmissionType, GearShifter, BUTTON_STATES

ButtonType = car.CarState.ButtonEvent.Type
EventName = car.CarEvent.EventName


class CarInterface(CarInterfaceBase):
  def __init__(self, CP, CarController, CarState):
    super().__init__(CP, CarController, CarState)

    if CP.networkLocation == NetworkLocation.fwdCamera:
      self.ext_bus = CANBUS.pt
      self.cp_ext = self.cp
    else:
      self.ext_bus = CANBUS.cam
      self.cp_ext = self.cp_cam

    self.buttonStatesPrev = BUTTON_STATES.copy()

  @staticmethod
  def _get_params(ret, candidate, fingerprint, car_fw, experimental_long, docs):
    ret.carName = "volkswagen"
    ret.radarUnavailable = True

    if candidate in PQ_CARS:
      # Set global PQ35/PQ46/NMS parameters
      ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.volkswagenPq)]
      ret.enableBsm = 0x3BA in fingerprint[0]  # SWA_1

      if 0x440 in fingerprint[0] or docs:  # Getriebe_1
        ret.transmissionType = TransmissionType.automatic
      else:
        ret.transmissionType = TransmissionType.manual

      if any(msg in fingerprint[1] for msg in (0x1A0, 0xC2)):  # Bremse_1, Lenkwinkel_1
        ret.networkLocation = NetworkLocation.gateway
      else:
        ret.networkLocation = NetworkLocation.fwdCamera

      # The PQ port is in dashcam-only mode due to a fixed six-minute maximum timer on HCA steering. An unsupported
      # EPS flash update to work around this timer, and enable steering down to zero, is available from:
      #   https://github.com/pd0wm/pq-flasher
      # It is documented in a four-part blog series:
      #   https://blog.willemmelching.nl/carhacking/2022/01/02/vw-part1/
      # Panda ALLOW_DEBUG firmware required.
      ret.dashcamOnly = True

    else:
      # Set global MQB parameters
      ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.volkswagen)]
      ret.enableBsm = 0x30F in fingerprint[0]  # SWA_01

      if 0xAD in fingerprint[0] or docs:  # Getriebe_11
        ret.transmissionType = TransmissionType.automatic
      elif 0x187 in fingerprint[0]:  # EV_Gearshift
        ret.transmissionType = TransmissionType.direct
      else:
        ret.transmissionType = TransmissionType.manual

      if any(msg in fingerprint[1] for msg in (0x40, 0x86, 0xB2, 0xFD)):  # Airbag_01, LWI_01, ESP_19, ESP_21
        ret.networkLocation = NetworkLocation.gateway
      else:
        ret.networkLocation = NetworkLocation.fwdCamera

    # Global lateral tuning defaults, can be overridden per-vehicle

    ret.steerActuatorDelay = 0.1
    ret.steerLimitTimer = 0.4
    ret.steerRatio = 15.6  # Let the params learner figure this out
    ret.lateralTuning.pid.kpBP = [0.]
    ret.lateralTuning.pid.kiBP = [0.]
    ret.lateralTuning.pid.kf = 0.00006
    ret.lateralTuning.pid.kpV = [0.6]
    ret.lateralTuning.pid.kiV = [0.2]

    # Global longitudinal tuning defaults, can be overridden per-vehicle

    ret.experimentalLongitudinalAvailable = ret.networkLocation == NetworkLocation.gateway or docs
    if experimental_long:
      # Proof-of-concept, prep for E2E only. No radar points available. Panda ALLOW_DEBUG firmware required.
      ret.openpilotLongitudinalControl = True
      ret.safetyConfigs[0].safetyParam |= Panda.FLAG_VOLKSWAGEN_LONG_CONTROL
      if ret.transmissionType == TransmissionType.manual:
        ret.minEnableSpeed = 4.5

    ret.pcmCruise = not ret.openpilotLongitudinalControl
    ret.customStockLongAvailable = True
    ret.stoppingControl = True
    ret.startingState = True
    ret.startAccel = 1.0
    ret.vEgoStarting = 1.0
    ret.vEgoStopping = 1.0
    ret.longitudinalTuning.kpV = [0.1]
    ret.longitudinalTuning.kiV = [0.0]

    # Per-chassis tuning values, override tuning defaults here if desired

    if candidate == CAR.ARTEON_MK1:
      ret.mass = 1733 + STD_CARGO_KG
      ret.wheelbase = 2.84

    elif candidate == CAR.ATLAS_MK1:
      ret.mass = 2011 + STD_CARGO_KG
      ret.wheelbase = 2.98

    elif candidate == CAR.CRAFTER_MK2:
      ret.mass = 2100 + STD_CARGO_KG
      ret.wheelbase = 3.64  # SWB, LWB is 4.49, TBD how to detect difference
      ret.minSteerSpeed = 50 * CV.KPH_TO_MS

    elif candidate == CAR.GOLF_MK7:
      ret.mass = 1397 + STD_CARGO_KG
      ret.wheelbase = 2.62

    elif candidate == CAR.JETTA_MK7:
      ret.mass = 1328 + STD_CARGO_KG
      ret.wheelbase = 2.71

    elif candidate == CAR.PASSAT_MK8:
      ret.mass = 1551 + STD_CARGO_KG
      ret.wheelbase = 2.79

    elif candidate == CAR.PASSAT_NMS:
      ret.mass = 1503 + STD_CARGO_KG
      ret.wheelbase = 2.80
      ret.minEnableSpeed = 20 * CV.KPH_TO_MS  # ACC "basic", no FtS
      ret.minSteerSpeed = 50 * CV.KPH_TO_MS
      ret.steerActuatorDelay = 0.2
      CarInterfaceBase.configure_torque_tune(candidate, ret.lateralTuning)

    elif candidate == CAR.POLO_MK6:
      ret.mass = 1230 + STD_CARGO_KG
      ret.wheelbase = 2.55

    elif candidate == CAR.SHARAN_MK2:
      ret.mass = 1639 + STD_CARGO_KG
      ret.wheelbase = 2.92
      ret.minSteerSpeed = 50 * CV.KPH_TO_MS
      ret.steerActuatorDelay = 0.2

    elif candidate == CAR.TAOS_MK1:
      ret.mass = 1498 + STD_CARGO_KG
      ret.wheelbase = 2.69

    elif candidate == CAR.TCROSS_MK1:
      ret.mass = 1150 + STD_CARGO_KG
      ret.wheelbase = 2.60

    elif candidate == CAR.TIGUAN_MK2:
      ret.mass = 1715 + STD_CARGO_KG
      ret.wheelbase = 2.74

    elif candidate == CAR.TOURAN_MK2:
      ret.mass = 1516 + STD_CARGO_KG
      ret.wheelbase = 2.79

    elif candidate == CAR.TRANSPORTER_T61:
      ret.mass = 1926 + STD_CARGO_KG
      ret.wheelbase = 3.00  # SWB, LWB is 3.40, TBD how to detect difference
      ret.minSteerSpeed = 14.0

    elif candidate == CAR.TROC_MK1:
      ret.mass = 1413 + STD_CARGO_KG
      ret.wheelbase = 2.63

    elif candidate == CAR.AUDI_A3_MK3:
      ret.mass = 1335 + STD_CARGO_KG
      ret.wheelbase = 2.61

    elif candidate == CAR.AUDI_Q2_MK1:
      ret.mass = 1205 + STD_CARGO_KG
      ret.wheelbase = 2.61

    elif candidate == CAR.AUDI_Q3_MK2:
      ret.mass = 1623 + STD_CARGO_KG
      ret.wheelbase = 2.68

    elif candidate == CAR.SEAT_ATECA_MK1:
      ret.mass = 1900 + STD_CARGO_KG
      ret.wheelbase = 2.64

    elif candidate == CAR.SEAT_LEON_MK3:
      ret.mass = 1227 + STD_CARGO_KG
      ret.wheelbase = 2.64

    elif candidate == CAR.SKODA_FABIA_MK4:
      ret.mass = 1266 + STD_CARGO_KG
      ret.wheelbase = 2.56

    elif candidate == CAR.SKODA_KAMIQ_MK1:
      ret.mass = 1265 + STD_CARGO_KG
      ret.wheelbase = 2.66

    elif candidate == CAR.SKODA_KAROQ_MK1:
      ret.mass = 1278 + STD_CARGO_KG
      ret.wheelbase = 2.66

    elif candidate == CAR.SKODA_KODIAQ_MK1:
      ret.mass = 1569 + STD_CARGO_KG
      ret.wheelbase = 2.79

    elif candidate == CAR.SKODA_OCTAVIA_MK3:
      ret.mass = 1388 + STD_CARGO_KG
      ret.wheelbase = 2.68

    elif candidate == CAR.SKODA_SCALA_MK1:
      ret.mass = 1192 + STD_CARGO_KG
      ret.wheelbase = 2.65

    elif candidate == CAR.SKODA_SUPERB_MK3:
      ret.mass = 1505 + STD_CARGO_KG
      ret.wheelbase = 2.84

    else:
      raise ValueError(f"unsupported car {candidate}")

    ret.autoResumeSng = ret.minEnableSpeed == -1
    ret.centerToFront = ret.wheelbase * 0.45
    return ret

  # returns a car.CarState
  def _update(self, c):
    ret = self.CS.update(self.cp, self.cp_cam, self.cp_ext, self.CP.transmissionType)
    self.CS = self.sp_update_params(self.CS)

    buttonEvents = []

    # Check for and process state-change events (button press or release) from
    # the turn stalk switch or ACC steering wheel/control stalk buttons.
    for button in self.CS.buttonStates:
      if self.CS.buttonStates[button] != self.buttonStatesPrev[button]:
        be = car.CarState.ButtonEvent.new_message()
        be.type = button
        be.pressed = self.CS.buttonStates[button]
        buttonEvents.append(be)

    self.CS.mads_enabled = self.get_sp_cruise_main_state(ret, self.CS)

    self.CS.accEnabled, buttonEvents = self.get_sp_v_cruise_non_pcm_state(ret, self.CS.accEnabled,
                                                                          buttonEvents, c.vCruise,
                                                                          enable_buttons=(ButtonType.setCruise, ButtonType.resumeCruise))

    if ret.cruiseState.available:
      if self.enable_mads:
        if not self.CS.prev_mads_enabled and self.CS.mads_enabled:
          self.CS.madsEnabled = True
        self.CS.madsEnabled = self.get_acc_mads(ret.cruiseState.enabled, self.CS.accEnabled, self.CS.madsEnabled)
      ret, self.CS = self.toggle_gac(ret, self.CS, bool(self.CS.gap_dist_button), 1, 3, 3, "-")
    else:
      self.CS.madsEnabled = False

    if not self.CP.pcmCruise or (self.CP.pcmCruise and self.CP.minEnableSpeed > 0) or not self.CP.pcmCruiseSpeed:
      if any(b.type == ButtonType.cancel for b in buttonEvents):
        self.CS.madsEnabled, self.CS.accEnabled = self.get_sp_cancel_cruise_state(self.CS.madsEnabled)
    if self.get_sp_pedal_disengage(ret):
      self.CS.madsEnabled, self.CS.accEnabled = self.get_sp_cancel_cruise_state(self.CS.madsEnabled)
      ret.cruiseState.enabled = False if self.CP.pcmCruise else self.CS.accEnabled

    if self.CP.pcmCruise and self.CP.minEnableSpeed > 0 and self.CP.pcmCruiseSpeed:
      if ret.gasPressed and not ret.cruiseState.enabled:
        self.CS.accEnabled = False
      self.CS.accEnabled = ret.cruiseState.enabled or self.CS.accEnabled

    ret, self.CS = self.get_sp_common_state(ret, self.CS, gap_button=(self.CS.gap_dist_button == 3))

    # MADS BUTTON
    if self.CS.out.madsEnabled != self.CS.madsEnabled:
      if self.mads_event_lock:
        buttonEvents.append(create_mads_event(self.mads_event_lock))
        self.mads_event_lock = False
    else:
      if not self.mads_event_lock:
        buttonEvents.append(create_mads_event(self.mads_event_lock))
        self.mads_event_lock = True

    ret.buttonEvents = buttonEvents

    events = self.create_common_events(ret, c, extra_gears=[GearShifter.eco, GearShifter.sport, GearShifter.manumatic],
                                       pcm_enable=False,
                                       enable_buttons=(ButtonType.setCruise, ButtonType.resumeCruise))

    events, ret = self.create_sp_events(self.CS, ret, events,
                                        enable_buttons=(ButtonType.setCruise, ButtonType.resumeCruise))

    # Low speed steer alert hysteresis logic
    if self.CP.minSteerSpeed > 0. and ret.vEgo < (self.CP.minSteerSpeed + 1.):
      self.low_speed_alert = True
    elif ret.vEgo > (self.CP.minSteerSpeed + 2.):
      self.low_speed_alert = False
    if self.low_speed_alert and self.CS.madsEnabled:
      events.add(EventName.belowSteerSpeed)

    if self.CS.CP.openpilotLongitudinalControl:
      if ret.vEgo < self.CP.minEnableSpeed + 0.5:
        events.add(EventName.belowEngageSpeed)
      if c.enabled and ret.vEgo < self.CP.minEnableSpeed:
        events.add(EventName.speedTooLow)

    ret.customStockLong = self.CS.update_custom_stock_long(self.CC.cruise_button, self.CC.final_speed_kph,
                                                           self.CC.target_speed, self.CC.v_set_dis,
                                                           self.CC.speed_diff, self.CC.button_type)

    ret.events = events.to_msg()

    # update previous car states
    self.buttonStatesPrev = self.CS.buttonStates.copy()

    return ret

  def apply(self, c, now_nanos):
    return self.CC.update(c, self.CS, self.ext_bus, now_nanos)
