import os

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import describe

from selfdrive.config import Conversions as CV

from tools.tuning.lat_settings import *

# For comparison with previous best
def old_feedforward(speed, angle):
  
  # sierra silverado combined
  # ANGLE = 0.06539361463056717
  # ANGLE_OFFSET = -0.8390269362439537
  # SIGMOID_SPEED = 0.023681877712247515
  # SIGMOID = 0.5709779025308087
  # SPEED = -0.0016656455765509301
  
  #sierra only
  # ANGLE = 0.07375408334531243
  # ANGLE_OFFSET = -0.43842460609320844
  # SIGMOID_SPEED = 0.015039986300916987
  # SIGMOID = 0.6154522080649616
  # SPEED = -0.00238195057681674
  
  # silverado only
  # ANGLE = 0.07017408594582242
  # ANGLE_OFFSET = -0.7108582322213549
  # SIGMOID_SPEED = 0.02534582973830592
  # SIGMOID = 0.5901819029949994
  # SPEED = -0.0026961086215487357
  # return feedforward(speed, angle, ANGLE, ANGLE_OFFSET, SIGMOID_SPEED, SIGMOID, SPEED)
  # return 0.0002 * (speed ** 2) * angle # old bolt and bolteuv
  # return 0.00004 * (speed ** 2) * angle # old silverado/sierra
  # return 0.000195 * (speed ** 2) * angle # old suburban

  return angle * 0.375

  # old volt sigmoid
  # x = angle * 0.02904609
  # sigmoid = x / (1 + np.fabs(x))
  # return 0.10006696 * sigmoid * (speed + 3.12485927)

  #old acadia sigmoid
  # desired_angle = 0.09760208 * angle
  # sigmoid = desired_angle / (1 + np.fabs(desired_angle))
  # return 0.04689655 * sigmoid * (speed + 10.028217)

def new_feedforward(speed, angle):
  return feedforward(speed, angle, ANGLE, ANGLE_OFFSET, SIGMOID_SPEED, SIGMOID, SPEED)

def feedforward(speed, angle, ANGLE, ANGLE_OFFSET, SIGMOID_SPEED, SIGMOID, SPEED):
  x = ANGLE * angle
  sigmoid = x / (1 + np.fabs(x))
  # sigmoid = np.arcsinh(x)
  return (SIGMOID_SPEED * sigmoid * speed) + (SIGMOID * sigmoid) + (SPEED * speed)

def _fit_kf(x_input, angle_gain, angle_offset, sigmoid_speed, sigmoid, speed_gain):
  speed, angle = x_input.copy()
  return feedforward(speed, angle, angle_gain, angle_offset, sigmoid_speed, sigmoid, speed_gain)

def fit(speed, angle, steer):
  print(f'speed: {len(speed) = }')
  print(f'angle: {len(angle) = }')
  print(f'steer: {len(steer) = }')
  print(f'speed: {describe(speed)}')
  print(f'angle: {describe(angle)}')
  print(f'steer: {describe(steer)}')

  global ANGLE, ANGLE_OFFSET, SIGMOID_SPEED, SIGMOID, SPEED
  params, _ = curve_fit(  # lgtm[py/mismatched-multiple-assignment] pylint: disable=unbalanced-tuple-unpacking
    _fit_kf,
    np.array([speed, angle]),
    np.array(steer),
    maxfev=9000,
  )
  ANGLE, ANGLE_OFFSET, SIGMOID_SPEED, SIGMOID, SPEED = params
  print(f'Fit: {params}')
  print(f"{ANGLE = }")
  print(f"{ANGLE_OFFSET = }")
  print(f"{SIGMOID_SPEED = }")
  print(f"{SIGMOID = }")
  print(f"{SPEED = }")

  old_residual = np.fabs(old_feedforward(speed, angle) - steer)
  new_residual = np.fabs(new_feedforward(speed, angle) - steer)
  old_mae = np.mean(old_residual)
  new_mae = np.mean(new_residual)
  print('MAE old {}, new {}'.format(round(old_mae, 4), round(new_mae, 4)))
  old_std = np.std(old_residual)
  new_std = np.std(new_residual)
  print('STD old {}, new {}'.format(round(old_std, 4), round(new_std, 4)))
  
  with open("plots/out.txt","a") as f:
    f.write(f"    {ANGLE = }\n")
    f.write(f"    {ANGLE_OFFSET = }\n")
    f.write(f"    {SIGMOID_SPEED = }\n")
    f.write(f"    {SIGMOID = }\n")
    f.write(f"    {SPEED = }\n")
    f.write('mean absolute error: old {}, new {}\n'.format(round(old_mae, 4), round(new_mae, 4)))
    f.write('standard deviation: old {}, new {}\n'.format(round(old_std, 4), round(new_std, 4)))
    f.write(f"fit computed using {len(speed)} points")

def plot(speed, angle, steer):
  if SPEED_PLOTS:
    os.system('rm plots/deg*')
    abs_angle = np.fabs(angle)
    abs_steer = np.fabs(steer)

    # if PLOT_ANGLE_DIST:
    #   sns.distplot([
    #       line['angle'] for line in data if abs(line['angle']) < 30
    #   ],
    #                bins=200)
    #   raise Exception

    res = 100

    # _angles = []
    # STEP = 1 # degrees
    # for a in range(0, 90, STEP):
    #   _angles.append([a, a + STEP])
    # _angles = np.r_[_angles]
    
    _angles = []
    STEP = 0.05 # degrees
    astart = 0.
    aend = 4.
    for a in np.linspace(astart, aend, num=int((aend-astart)/STEP)).tolist():
      _angles.append([a, a + STEP])
    _angles = np.r_[_angles]

    for angle_range in _angles:
      # start = round(angle_range[0])
      # end = round(angle_range[1])
      # angle_range_str = f'deg {start:02d}-{end:02d}'
      start = angle_range[0]
      end = angle_range[1]
      angle_range_str = f'lat_accel {start:.2f}-{end:.2f}'
      mask = (angle_range[0] <= abs_angle) & (abs_angle <= angle_range[1])

      plot_speed = speed[mask]
      plot_angle = abs_angle[mask]
      plot_steer = abs_steer[mask]

      params = None
      if FIT_EACH_PLOT and sum(mask) > 4:
        try:
          global ANGLE, ANGLE_OFFSET, SIGMOID_SPEED, SIGMOID, SPEED
          params, _ = curve_fit(  # lgtm[py/mismatched-multiple-assignment] pylint: disable=unbalanced-tuple-unpacking
            _fit_kf,
            np.array([plot_speed, plot_angle]),
            np.array(plot_steer),
            maxfev=9000,
          )
          ANGLE, ANGLE_OFFSET, SIGMOID_SPEED, SIGMOID, SPEED = params
        except RuntimeError as e:
          print(e)
          continue

      print(f'{angle_range_str} ({len(plot_speed)}): {params}')
      plt.figure(figsize=(12,8))
      plt.scatter(plot_speed * CV.MS_TO_MPH,
                  plot_steer,
                  label=angle_range_str,
                  color='black',
                  s=1.)

      _x_ff = np.linspace(0, 80, res)
      _y_ff = [
          old_feedforward(_i, np.mean(angle_range))
          for _i in _x_ff
      ]
      plt.plot(_x_ff * CV.MS_TO_MPH,
               _y_ff,
               color='red',
               label='old')

      _y_ff = [
          new_feedforward(_i, np.mean(angle_range))
          for _i in _x_ff
      ]
      plt.plot(_x_ff * CV.MS_TO_MPH,
               _y_ff,
               color='blue',
               label='new')

      plt.title(angle_range_str)
      plt.legend(loc='upper left')
      plt.xlabel('speed (mph)')
      plt.ylabel('steer')
      plt.ylim(0., 1.5)
      plt.xlim(SPEED_MIN, SPEED_MAX)
      plt.grid(axis='x', color='0.95')
      plt.grid(axis='y', color='0.95')
      if not os.path.isdir('plots'):
        os.mkdir('plots')
      plt.savefig(f'plots/{angle_range_str}.png')
      plt.close()

  if ANGLE_PLOTS:
    os.system('rm plots/mph*')
    # if PLOT_ANGLE_DIST:
    #   sns.displot([
    #       line['angle'] for line in data if abs(line['angle']) < 30
    #   ],
    #               bins=200)
    #   raise Exception

    res = 1000

    _speeds = []
    STEP = 1 # mph
    for s in range(SPEED_MIN, SPEED_MAX, STEP):
      _speeds.append([s, s + STEP])
    _speeds = np.r_[_speeds]

    for speed_range in _speeds:
      start = round(speed_range[0])
      end = round(speed_range[1])
      speed_range_str = f'mph {start:02d}-{end:02d}'
      mask = (speed_range[0] <= speed * CV.MS_TO_MPH) & (speed * CV.MS_TO_MPH <= speed_range[1])

      plot_speed = speed[mask]
      plot_angle = angle[mask]
      plot_steer = steer[mask]

      params = None
      if FIT_EACH_PLOT and sum(mask) > 4:
        try:
          params, _ = curve_fit( # lgtm[py/mismatched-multiple-assignment] pylint: disable=unbalanced-tuple-unpacking
            _fit_kf,
            np.array([plot_speed, plot_angle]),
            np.array(plot_steer),
            maxfev=9000,
          )
          ANGLE, SIGMOID_SPEED, SIGMOID, SPEED = params
        except RuntimeError as e:
          print(e)
          continue

      print(f'{speed_range_str} ({len(plot_speed)}): {params}')
      plt.figure(figsize=(12,8))
      plt.scatter(plot_angle, plot_steer, label=speed_range_str, color='black', s=1.)

      _x_ff = np.linspace(-180, 180, res)
      _y_ff = [
          old_feedforward(np.mean(speed_range) * CV.MPH_TO_MS, _i) for _i in _x_ff
      ]
      plt.plot(
          _x_ff,
          _y_ff,
          color='red',
          label='old'
      )
      _y_ff = [
          new_feedforward(np.mean(speed_range) * CV.MPH_TO_MS, _i)
          for _i in _x_ff
      ]
      plt.plot(_x_ff, _y_ff, color='blue', label='new')

      plt.title(speed_range_str)
      plt.legend(loc='lower right')
      # plt.xlabel('angle (deg)')
      plt.xlabel('lateral acceleration (m/s^2)')
      plt.ylabel('steer')
      plt.ylim(-1.5, 1.5)
      # plt.xlim(-90.,90.)
      plt.xlim(-4.,4.)
      plt.grid(axis='x', color='0.95')
      plt.grid(axis='y', color='0.95')
      # plt.xlim(-max(abs(plot_angle)), max(abs(plot_angle)))
      plt.savefig(f'plots/{speed_range_str}.png')
      plt.close()

  if SPEED_PLOTS or ANGLE_PLOTS:
    # Create animations
    cmds = [
      'rm -rf ~/Downloads/plots',
      'convert -delay 8 plots/deg*.png deg-up.gif',
      'convert -delay 8 plots/lat*.png deg-up.gif',
      'convert -reverse deg-up.gif deg-down.gif',
      'convert -loop -1 deg-up.gif deg-down.gif deg.gif',
      'convert -delay 8 plots/mph*.png mph-up.gif',
      'convert -reverse mph-up.gif mph-down.gif',
      'convert -loop -1 mph-up.gif mph-down.gif mph.gif',
      'convert -loop -1 deg.gif mph.gif solution.gif',
      'mv *.gif plots/',
      'mv plots ~/Downloads/',
      'rm -f ~/Downloads/plots/deg*.png',
      'rm -f ~/Downloads/plots/lat*.png',
      'rm -f ~/Downloads/plots/mph*.png',
      'rm -f regularized'
    ]
    for cmd in cmds:
      print(cmd)
      os.system(cmd)
