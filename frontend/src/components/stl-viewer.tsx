"use client";

import { useRef, useState, Suspense } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";
import { STLLoader } from "three-stdlib";
import { Loader2 } from "lucide-react";

function Mesh({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const meshRef = useRef<THREE.Mesh>(null);

  // Center and scale
  const [centered, setCentered] = useState(false);

  useFrame(() => {
    if (!meshRef.current || centered) return;
    const box = new THREE.Box3().setFromObject(meshRef.current);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = maxDim > 0 ? 10 / maxDim : 1;
    meshRef.current.scale.setScalar(scale);

    const center = new THREE.Vector3();
    box.getCenter(center);
    meshRef.current.position.sub(center.multiplyScalar(scale));
    setCentered(true);
  });

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial color="#888888" roughness={0.4} metalness={0.1} />
    </mesh>
  );
}

function Scene({ url }: { url: string }) {
  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0, 20]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <directionalLight position={[-10, -10, -5]} intensity={0.3} />
      <Suspense fallback={null}>
        <Mesh url={url} />
      </Suspense>
      <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} />
    </>
  );
}

export function STLViewer({ url }: { url: string }) {
  return (
    <div className="relative h-full w-full">
      <Canvas className="h-full w-full">
        <Scene url={url} />
      </Canvas>
      <Suspense
        fallback={
          <div className="absolute inset-0 flex items-center justify-center bg-muted/50">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <div />
      </Suspense>
    </div>
  );
}
