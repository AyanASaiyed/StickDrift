import * as THREE from 'three'

/** The sun used in every scene (Blender: sun rotated 35/10/25 degrees), plus soft sky fill light. */
export function addSun(scene, { intensity = 6, fill = 1.6, extent = 16, sky = 0xbfd8ff, ground = 0x5a4a38 } = {}) {
  const dir = new THREE.Vector3(0, 0, -1).applyEuler(new THREE.Euler((35 * Math.PI) / 180, (10 * Math.PI) / 180, (25 * Math.PI) / 180))
  const sun = new THREE.DirectionalLight(0xffffff, intensity)
  sun.position.copy(dir).multiplyScalar(-40)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  const c = sun.shadow.camera
  c.left = -extent
  c.right = extent
  c.top = extent
  c.bottom = -extent
  c.near = 1
  c.far = 120
  sun.shadow.bias = -0.0004
  sun.shadow.normalBias = 0.03
  scene.add(sun, sun.target)
  scene.add(new THREE.HemisphereLight(sky, ground, fill))
  return sun
}
