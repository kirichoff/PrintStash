"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { Canvas, useLoader } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";
import { STLLoader } from "three-stdlib";
import { Loader2 } from "lucide-react";

const box = new THREE.Box3();
const sizeVec = new THREE.Vector3();
const centerVec = new THREE.Vector3();

function Mesh({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const meshRef = useRef<THREE.Mesh>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!meshRef.current || ready) return;
    box.setFromObject(meshRef.current);
    box.getSize(sizeVec);
    const maxDim = Math.max(sizeVec.x, sizeVec.y, sizeVec.z);
    const scale = maxDim > 0 ? 10 / maxDim : 1;
    meshRef.current.scale.setScalar(scale);
    box.getCenter(centerVec);
    meshRef.current.position.sub(centerVec.multiplyScalar(scale));
    setReady(true);
  }, [geometry, ready]);

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
      <Suspense
        fallback={
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-[var(--on-surface-variant)]" />
          </div>
        }
      >
        <Canvas className="h-full w-full">
          <Scene url={url} />
        </Canvas>
      </Suspense>
    </div>
  );
}
