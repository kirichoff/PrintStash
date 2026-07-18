"use client";

import React, {
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Canvas, useLoader, useThree } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera, Text } from "@react-three/drei";
import * as THREE from "three";
import { STLLoader } from "three-stdlib";
import { AlertTriangle, Loader2 } from "lucide-react";

import { authHeaders } from "@/lib/api/request";
import { getPlateLayout } from "@/lib/api/plates";
import type {
  STLViewerControls,
  ViewerDisplayMode,
} from "@/components/stl-viewer";
import type { PlateLayoutRead } from "@/types";

const DEFAULT_CAMERA_POSITION = new THREE.Vector3(0.9, 0.8, 1.1);
const ZOOM_FACTOR = 0.75;
// The whole multi-plate layout is normalized so its largest span equals this
// many world units — keeps the camera framing stable regardless of bed size.
const LAYOUT_SIZE = 12;
// Visible gap between adjacent plates, in millimetres.
const PLATE_GAP_MM = 40;

export interface PlatedViewerProps {
  fileId: number;
  printerBedMm: { x: number; y: number };
  onControlsReady?: (api: STLViewerControls) => void;
  displayMode?: ViewerDisplayMode;
  showGrid?: boolean;
  screenshotName?: string;
  /** Rendered when the plate layout can't be used (fetch error, single blob). */
  fallback: React.ReactNode;
}

interface PlacedObject {
  url: string;
  // Position of the object's origin in layout-world units (already scaled).
  position: [number, number, number];
}

interface PlateLayout {
  index: number;
  // Bed rectangle centre in layout-world units.
  center: [number, number];
  objects: PlacedObject[];
}

interface ComputedLayout {
  plates: PlateLayout[];
  bedX: number; // bed width in world units
  bedZ: number; // bed depth in world units
  unitsPerMm: number;
}

/** Lay plates out in a horizontal row, all sharing one mm→world scale. */
function computeLayout(
  data: PlateLayoutRead,
  bedMm: { x: number; y: number },
): ComputedLayout {
  const n = data.plates.length;
  const gap = PLATE_GAP_MM;
  // Total layout footprint in mm (row of beds with gaps between them).
  const totalWidthMm = n * bedMm.x + (n - 1) * gap;
  const totalDepthMm = bedMm.y;
  const maxSpanMm = Math.max(totalWidthMm, totalDepthMm) || 1;
  const unitsPerMm = LAYOUT_SIZE / maxSpanMm;

  const bedX = bedMm.x * unitsPerMm;
  const bedZ = bedMm.y * unitsPerMm;
  const gapU = gap * unitsPerMm;
  const stride = bedX + gapU;
  // Centre the row on the origin.
  const startCenterX = -((n - 1) * stride) / 2;

  const plates: PlateLayout[] = data.plates.map((plate, i) => {
    const centerX = startCenterX + i * stride;
    const objects: PlacedObject[] = plate.objects.map((obj) => {
      // The build-item translation places the object on the *shared* bed; make
      // it relative to this plate's own bed centre so each plate reads cleanly.
      const relX = (obj.origin_mm[0] - bedMm.x / 2) * unitsPerMm;
      const relY = (obj.origin_mm[1] - bedMm.y / 2) * unitsPerMm;
      const relZ = obj.origin_mm[2] * unitsPerMm;
      return {
        url: obj.stl_url,
        // gcode/mesh Z-up → three Y-up: world Y = bed Z, world Z = -(bed Y).
        position: [centerX + relX, relZ, -relY],
      };
    });
    return { index: plate.index, center: [centerX, 0], objects };
  });

  return { plates, bedX, bedZ, unitsPerMm };
}

function PlateObjectMesh({
  url,
  position,
  displayMode,
}: {
  url: string;
  position: [number, number, number];
  displayMode: ViewerDisplayMode;
}) {
  const geometry = useLoader(STLLoader, url, (loader) => {
    loader.setRequestHeader(authHeaders());
  });
  const meshRef = useRef<THREE.Mesh>(null);

  useEffect(() => {
    return () => geometry.dispose();
  }, [geometry]);

  // Meshes are authored Z-up; stand them upright in this Y-up scene, matching
  // the single-mesh STLViewer.
  return (
    <mesh ref={meshRef} geometry={geometry} position={position} rotation={[-Math.PI / 2, 0, 0]}>
      <meshStandardMaterial
        color="#8a93a6"
        roughness={0.45}
        metalness={0.1}
        wireframe={displayMode === "wireframe"}
        transparent={displayMode === "xray"}
        opacity={displayMode === "xray" ? 0.3 : 1}
        depthWrite={displayMode !== "xray"}
      />
    </mesh>
  );
}

function Bed({
  center,
  bedX,
  bedZ,
  label,
  showGrid,
}: {
  center: [number, number];
  bedX: number;
  bedZ: number;
  label: string;
  showGrid: boolean;
}) {
  const [cx, cz] = center;
  const divisions = Math.max(4, Math.round(Math.max(bedX, bedZ) * 2));
  return (
    <group position={[cx, 0, cz]}>
      {showGrid && (
        <gridHelper args={[Math.max(bedX, bedZ), divisions, "#94a3b8", "#475569"]} />
      )}
      {/* Bed outline so plate boundaries are unmistakable. */}
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(bedX, 0.001, bedZ)]} />
        <lineBasicMaterial color="#64748b" />
      </lineSegments>
      <Text
        position={[0, 0.02, bedZ / 2 + 0.35]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={Math.max(0.25, bedX * 0.08)}
        color="#94a3b8"
        anchorX="center"
        anchorY="middle"
      >
        {label}
      </Text>
    </group>
  );
}

function PlatedScene({
  layout,
  displayMode,
  showGrid,
  screenshotName,
  onControlsReady,
}: {
  layout: ComputedLayout;
  displayMode: ViewerDisplayMode;
  showGrid: boolean;
  screenshotName: string;
  onControlsReady?: (api: STLViewerControls) => void;
}) {
  const orbitRef = useRef<any>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera>(null);
  const { gl, scene, camera } = useThree();

  const controlsApi = useMemo<STLViewerControls>(
    () => ({
      zoomIn: () => {
        if (cameraRef.current) {
          cameraRef.current.position.multiplyScalar(ZOOM_FACTOR);
          orbitRef.current?.update();
        }
      },
      zoomOut: () => {
        if (cameraRef.current) {
          cameraRef.current.position.multiplyScalar(1 / ZOOM_FACTOR);
          orbitRef.current?.update();
        }
      },
      resetView: () => {
        orbitRef.current?.reset();
        if (cameraRef.current) {
          cameraRef.current.position.copy(
            DEFAULT_CAMERA_POSITION.clone().multiplyScalar(LAYOUT_SIZE),
          );
          cameraRef.current.lookAt(0, 0, 0);
          orbitRef.current?.update();
        }
      },
      fit: () => {
        const cam = cameraRef.current;
        if (!cam) return;
        const dir = cam.position.clone().normalize();
        if (dir.lengthSq() === 0) dir.copy(DEFAULT_CAMERA_POSITION).normalize();
        dir.multiplyScalar(LAYOUT_SIZE * 1.4);
        orbitRef.current?.target?.set(0, 0, 0);
        cam.position.copy(dir);
        cam.lookAt(0, 0, 0);
        orbitRef.current?.update();
      },
      screenshot: () => {
        gl.render(scene, camera);
        const dataUrl = gl.domElement.toDataURL("image/png");
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = `${screenshotName || "model"}.png`;
        document.body.appendChild(link);
        link.click();
        link.remove();
      },
    }),
    [gl, scene, camera, screenshotName],
  );

  useEffect(() => {
    onControlsReady?.(controlsApi);
  }, [onControlsReady, controlsApi]);

  // Frame the whole layout once on mount.
  const fittedRef = useRef(false);
  useEffect(() => {
    if (!fittedRef.current) {
      controlsApi.fit();
      fittedRef.current = true;
    }
  }, [controlsApi]);

  return (
    <>
      <PerspectiveCamera
        ref={cameraRef}
        makeDefault
        position={
          DEFAULT_CAMERA_POSITION.clone()
            .multiplyScalar(LAYOUT_SIZE)
            .toArray() as [number, number, number]
        }
      />
      <ambientLight intensity={0.5} />
      <hemisphereLight args={["#d4e8ff", "#1a1a2e", 0.4]} />
      <directionalLight position={[8, 12, 6]} intensity={1.2} />
      <directionalLight position={[-6, -4, -8]} intensity={0.25} />
      {layout.plates.map((plate) => (
        <group key={plate.index}>
          <Bed
            center={plate.center}
            bedX={layout.bedX}
            bedZ={layout.bedZ}
            label={`Plate ${plate.index}`}
            showGrid={showGrid}
          />
          <Suspense fallback={null}>
            {plate.objects.map((obj, i) => (
              <PlateObjectMesh
                key={`${plate.index}-${i}`}
                url={obj.url}
                position={obj.position}
                displayMode={displayMode}
              />
            ))}
          </Suspense>
        </group>
      ))}
      <OrbitControls ref={orbitRef} enablePan enableZoom enableRotate />
    </>
  );
}

class PlateErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode; fallback: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}

export function PlatedViewer({
  fileId,
  printerBedMm,
  onControlsReady,
  displayMode = "solid",
  showGrid = true,
  screenshotName = "model",
  fallback,
}: PlatedViewerProps) {
  const [layoutData, setLayoutData] = useState<PlateLayoutRead | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    setLayoutData(null);
    getPlateLayout(fileId)
      .then((data) => {
        if (alive) setLayoutData(data);
      })
      .catch(() => {
        if (alive) setFailed(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [fileId]);

  const layout = useMemo(
    () => (layoutData ? computeLayout(layoutData, printerBedMm) : null),
    [layoutData, printerBedMm],
  );

  // Nothing meaningful to separate (single object on one plate) → single view.
  const trivial =
    layoutData !== null &&
    layoutData.plate_count <= 1 &&
    layoutData.object_count <= 1;

  if (loading) {
    return (
      <div className="relative h-full w-full">
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-on-surface-variant" />
        </div>
      </div>
    );
  }

  if (failed || trivial || !layout || layout.plates.length === 0) {
    return <>{fallback}</>;
  }

  return (
    <div className="relative h-full w-full">
      <PlateErrorBoundary
        fallback={
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-on-surface-variant">
            <AlertTriangle className="h-8 w-8" />
            <span className="font-mono text-xs">Failed to load plates</span>
          </div>
        }
      >
        <Canvas className="h-full w-full" gl={{ preserveDrawingBuffer: true }}>
          <PlatedScene
            layout={layout}
            displayMode={displayMode}
            showGrid={showGrid}
            screenshotName={screenshotName}
            onControlsReady={onControlsReady}
          />
        </Canvas>
      </PlateErrorBoundary>
    </div>
  );
}
