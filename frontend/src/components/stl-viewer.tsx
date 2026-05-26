"use client";

import React, { Suspense, useEffect, useRef } from "react";
import { Canvas, useLoader } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";
import { STLLoader } from "three-stdlib";
import { AlertTriangle, Loader2 } from "lucide-react";

export interface STLViewerControls {
  zoomIn: () => void;
  zoomOut: () => void;
  resetView: () => void;
}

const DEFAULT_CAMERA_POSITION = new THREE.Vector3(0, 0, 20);
const ZOOM_FACTOR = 0.75;

const box = new THREE.Box3();
const sizeVec = new THREE.Vector3();
const centerVec = new THREE.Vector3();

function Mesh({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const meshRef = useRef<THREE.Mesh>(null);

  useEffect(() => {
    if (!meshRef.current) return;
    const mesh = meshRef.current;
    mesh.scale.setScalar(1);
    mesh.position.set(0, 0, 0);
    mesh.updateMatrixWorld();

    box.setFromObject(mesh);
    box.getSize(sizeVec);

    const maxDim = Math.max(sizeVec.x, sizeVec.y, sizeVec.z);
    const scale = maxDim > 0 ? 10 / maxDim : 1;

    mesh.scale.setScalar(scale);
    box.getCenter(centerVec);
    mesh.position.sub(centerVec.multiplyScalar(scale));
  }, [geometry]);

  useEffect(() => {
    return () => {
      geometry.dispose();
    };
  }, [geometry]);

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial color="#888888" roughness={0.4} metalness={0.1} />
    </mesh>
  );
}

function Scene({
  url,
  onControlsReady,
}: {
  url: string;
  onControlsReady?: (api: STLViewerControls) => void;
}) {
  const orbitRef = useRef<any>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera>(null);

  const controlsApi: STLViewerControls = {
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
        cameraRef.current.position.copy(DEFAULT_CAMERA_POSITION);
        cameraRef.current.lookAt(0, 0, 0);
        orbitRef.current?.update();
      }
    },
  };

  useEffect(() => {
    if (onControlsReady) {
      onControlsReady(controlsApi);
    }
  }, [onControlsReady]);

  return (
    <>
      <PerspectiveCamera ref={cameraRef} makeDefault position={DEFAULT_CAMERA_POSITION.toArray() as [number, number, number]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <directionalLight position={[-10, -10, -5]} intensity={0.3} />
      <Suspense fallback={null}>
        <Mesh url={url} />
      </Suspense>
      <OrbitControls ref={orbitRef} enablePan={true} enableZoom={true} enableRotate={true} />
    </>
  );
}

interface MeshErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface MeshErrorBoundaryState {
  hasError: boolean;
}

class MeshErrorBoundary extends React.Component<MeshErrorBoundaryProps, MeshErrorBoundaryState> {
  constructor(props: MeshErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): MeshErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-[var(--on-surface-variant)]">
            <AlertTriangle className="h-8 w-8" />
            <span className="font-mono text-xs">Failed to load 3D preview</span>
          </div>
        )
      );
    }
    return this.props.children;
  }
}

export function STLViewer({
  url,
  onControlsReady,
}: {
  url: string;
  onControlsReady?: (api: STLViewerControls) => void;
}) {
  return (
    <div className="relative h-full w-full">
      <MeshErrorBoundary>
        <Suspense
          fallback={
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-[var(--on-surface-variant)]" />
            </div>
          }
        >
          <Canvas className="h-full w-full">
            <Scene url={url} onControlsReady={onControlsReady} />
          </Canvas>
        </Suspense>
      </MeshErrorBoundary>
    </div>
  );
}
