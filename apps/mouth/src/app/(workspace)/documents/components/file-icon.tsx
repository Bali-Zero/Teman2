import { Image, FileSpreadsheet, Presentation, FileText, FileCode, File, Users, Briefcase, TrendingUp, Scale, Settings, Building2 } from 'lucide-react';
import type { FileItem } from '@/lib/api/drive/drive.types';

// Department color mapping - matches the organization structure
export const DEPARTMENT_COLORS: Record<string, { primary: string; secondary: string; icon: typeof Users; label: string }> = {
    'BOARD': {
          primary: '#8B5CF6', // Violet
          secondary: '#A78BFA',
          icon: Building2,
          label: 'Board'
    },
    'CRM': {
          primary: '#3B82F6', // Blue
          secondary: '#60A5FA',
          icon: Users,
          label: 'CRM'
    },
    'MARKETING': {
          primary: '#EC4899', // Pink
          secondary: '#F472B6',
          icon: TrendingUp,
          label: 'Marketing'
    },
    'PERATURAN': {
          primary: '#10B981', // Emerald
          secondary: '#34D399',
          icon: Scale,
          label: 'Peraturan'
    },
    'SETUP TEAM': {
          primary: '#F59E0B', // Amber
          secondary: '#FBBF24',
          icon: Settings,
          label: 'Setup Team'
    },
    'TAX DEPARTMENT': {
          primary: '#EF4444', // Red
          secondary: '#F87171',
          icon: Briefcase,
          label: 'Tax Department'
    },
};

// Get department info from folder name
export function getDepartmentInfo(folderName: string) {
    const upperName = folderName.toUpperCase();
    for (const [key, value] of Object.entries(DEPARTMENT_COLORS)) {
          if (upperName.includes(key) || upperName === key) {
                  return value;
          }
    }
    return null;
}

// Modern 3D folder with department colors
interface DepartmentFolderProps {
    className?: string;
    primaryColor?: string;
    secondaryColor?: string;
    DepartmentIcon?: typeof Users;
}

export function DepartmentFolder({
    className,
    primaryColor = '#F59E0B',
    secondaryColor = '#FBBF24',
    DepartmentIcon
}: DepartmentFolderProps) {
    return (
          <div className={`relative ${className}`}>
                  <svg viewBox="0 0 64 64" className="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
                    {/* Shadow */}
                          <ellipse cx="32" cy="58" rx="24" ry="4" fill="black" opacity="0.1" />
                  
                    {/* Back panel with gradient */}
                          <defs>
                                    <linearGradient id={`folder-grad-${primaryColor}`} x1="0%" y1="0%" x2="100%" y2="100%">
                                                <stop offset="0%" stopColor={secondaryColor} />
                                                <stop offset="100%" stopColor={primaryColor} />
                                    </linearGradient>linearGradient>
                                    <filter id="folder-shadow" x="-20%" y="-20%" width="140%" height="140%">
                                                <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.2" />
                                    </filter>filter>
                          </defs>defs>
                  
                    {/* Back panel */}
                          <path
                                      d="M6 16C6 13.7909 7.79086 12 10 12H24L30 18H54C56.2091 18 58 19.7909 58 22V50C58 52.2091 56.2091 54 54 54H10C7.79086 54 6 52.2091 6 50V16Z"
                                      fill={primaryColor}
                                      filter="url(#folder-shadow)"
                                    />
                  
                    {/* Front panel with gradient */}
                          <path
                                      d="M6 22C6 19.7909 7.79086 18 10 18H54C56.2091 18 58 19.7909 58 22V50C58 52.2091 56.2091 54 54 54H10C7.79086 54 6 52.2091 6 50V22Z"
                                      fill={`url(#folder-grad-${primaryColor})`}
                                    />
                  
                    {/* Top shine */}
                          <path
                                      d="M10 18H54C56.2091 18 58 19.7909 58 22V24H6V22C6 19.7909 7.79086 18 10 18Z"
                                      fill="white"
                                      opacity="0.2"
                                    />
                  
                    {/* Inner line detail */}
                          <path
                                      d="M10 26H54"
                                      stroke={primaryColor}
                                      strokeWidth="1"
                                      opacity="0.3"
                                    />
                  </svg>svg>
          
            {/* Department icon overlay */}
            {DepartmentIcon && (
                    <div className="absolute inset-0 flex items-center justify-center pt-2">
                              <DepartmentIcon className="w-1/3 h-1/3 text-white/90 drop-shadow-sm" strokeWidth={1.5} />
                    </div>div>
                )}
          </div>div>
        );
}

// Standard Windows-style filled folder icon
function WindowsFolder({ className }: { className?: string }) {
    return (
          <svg viewBox="0 0 48 48" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Shadow */}
                <ellipse cx="24" cy="42" rx="16" ry="2" fill="black" opacity="0.1" />
          
            {/* Back panel shadow */}
                <path
                          d="M4 12C4 10.8954 4.89543 10 6 10H18L22 14H42C43.1046 14 44 14.8954 44 16V38C44 39.1046 43.1046 40 42 40H6C4.89543 40 4 39.1046 4 38V12Z"
                          fill="#D97706"
                        />
            {/* Front panel */}
                <path
                          d="M4 16C4 14.8954 4.89543 14 6 14H42C43.1046 14 44 14.8954 44 16V38C44 39.1046 43.1046 40 42 40H6C4.89543 40 4 39.1046 4 38V16Z"
                          fill="#F59E0B"
                        />
            {/* Top highlight */}
                <path
                          d="M6 14H18L22 10H6C4.89543 10 4 10.8954 4 12V16C4 14.8954 4.89543 14 6 14Z"
                          fill="#FBBF24"
                        />
            {/* Inner shadow for deipmtpho r*t/ }{
              I m a g e ,< pFaitlhe
              S p r e a d s h ede=t",M 6P r1e8sHe4n2tVa2t0iHo6nV,1 8FZi"l
              e T e x t ,   F iflielClo=d"e#,D 9F7i7l0e6," 
              U s e r s ,   B roipeafcciatsye=," 0T.r3e"n
              d i n g U p ,/ >S
              c a l e ,< /Ssevtgt>i
              n g s),; 
              B}u
              i
              ledxipnogr2t  }f ufnrcotmi o'nl ugceitdFei-lreeIaccotn'(;f
              iilmep:o rFti lteyIptee m{,  FsiilzeeI:t e'ms m}'  f|r o'ml g''@ /=l i'bl/ga'p)i /{d
              r i vceo/ndsrti vmei.mteyTpyepse' ;=
               
               f/i/l eD.empiamret_mteynpte  c|o|l o'r' ;m
               a p pcionngs t-  smiaztecChleass st h=e  soirzgea n=i=z=a t'isomn'  s?t r'uhc-t5u rwe-
               5e'x p:o r'th -c1o2n swt- 1D2E'P;A
               R
               T M EiNfT _(CfOiLlOeR.Si:s _Rfeoclodredr<)s t{r
               i n g ,  /{/  pCrhiemcakr yi:f  sittr'isn ga;  dseepcaorntdmaernyt:  fsotlrdienrg
               ;   i c ocno:n stty pdeeopft IUnsfeor s=;  gleatbDeelp:a rsttmreinntgI n}f>o (=f i{l
               e . n'aBmOeA)R;D
               ' :   { 
               i f   ( dperpitmIanrfyo:)  '{#
               8 B 5 C F 6 'r,e t/u/r nV i(o
               l e t 
                        s<eDceopnadratrmye:n t'F#oAl7d8eBrF
                        A ' , 
                                 i c ocnl:a sBsuNialmdei=n{gs2i,z
                                 e C l a slsa}b
                                 e l :   ' B o a r d 'p
                                 r i m}a,r
                                 y C o'lCoRrM='{:d e{p
                                 t I n f op.rpirmiamrayr:y }'
                                 # 3 B 8 2 F 6 ' ,   /s/e cBolnudea
                                 r y C o lsoerc=o{nddeaprtyI:n f'o#.6s0eAc5oFnAd'a,r
                                 y } 
                                     i c o n :   U s eDresp,a
                                     r t m e nltaIbceoln:= {'dCeRpMt'I
                                     n f o}.,i
                                     c o n'}M
                                     A R K E T I N G '/:> 
                                     { 
                                              p)r;i
                                              m a r y :} 
                                              ' # E C 4r8e9t9u'r,n  /</W iPnidnokw
                                              s F o l dseerc ocnldaasrsyN:a m'e#=F{4s7i2zBe6C'l,a
                                              s s }   /i>c;o
                                              n :  }T
                                              r e nidfi n(gmUipm,e
                                              T y p e .lianbcellu:d e'sM(a'rikmeatgien'g)')
                                                { 
                                                } , 
                                                    r'ePtEuRrAnT U<RIAmNa'g:e  {c
                                                    l a s s Nparmiem=a{r`y$:{ s'i#z1e0CBl9a8s1s'},  t/e/x tE-mpeirnakl-d5
                                                    0 0 ` }  s/e>c;o
                                                    n d a}r
                                                    y :  i'f# 3(4mDi3m9e9T'y,p
                                                    e . i n cilcuodne:s (S'csaplree,a
                                                    d s h e elta'b)e l|:|  'mPiemreaTtyuprea.ni'n
                                                    c l u}d,e
                                                    s ( ''eSxEcTeUlP' )T)E A{M
                                                    ' :   { 
                                                    r e t u rpnr i<mFairlye:S p'r#eFa5d9sEh0eBe't,  c/l/a sAsmNbaemre
                                                    = { ` $ {sseiczoenCdlaarsys:}  't#eFxBtB-Fg2r4e'e,n
                                                    - 5 0 0 `i}c o/n>:; 
                                                    S e t}t
                                                    i n gisf, 
                                                    ( m i m elTaybpeel.:i n'cSleutdueps (T'eparme's
                                                    e n t}a,t
                                                    i o n''T)A)X  {D
                                                    E P A R TrMeEtNuTr'n:  <{P
                                                    r e s e nptraitmiaorny :c l'a#sEsFN4a4m4e4='{,` $/{/s iRzeedC
                                                    l a s s }s etceoxntd-ayreyl:l o'w#-F580701`7}1 '/,>
                                                    ; 
                                                         }i
                                                         c o ni:f  B(rmiiemfecTayspee,.
                                                         i n c l uldaebse(l':d o'cTuamxe nDte'p)a r|t|m emnitm'e
                                                         T y p}e,.
                                                         i}n;c
                                                         l
                                                         u/d/e sG(e'tw odredp'a)r)t m{e
                                                         n t   i nrfeot ufrrno m< FfiolledTeerx tn acmlea
                                                         sesxNpaomret= {f`u$n{cstiizoenC lgaestsD}e ptaerxttm-ebnltuIen-f5o0(0f`o}l d/e>r;N
                                                         a m e}:
                                                           s tirfi n(gm)i m{e
                                                           T y pceo.nisntc luupdpeesr(N'apmdef '=) )f o{l
                                                           d e r N armeet.utronU p<pFeirlCeaTseex(t) ;c
                                                           l a sfsoNra m(ec=o{n`s$t{ s[ikzeeyC,l avsasl}u et]e xotf- rOebdj-e5c0t0.`e}n t/r>i;e
                                                           s ( D}E
                                                           P A RiTfM E(N
                                                           T _ C O LmOiRmSe)T)y p{e
                                                           . i n c liufd e(su(p'pceordNea'm)e .|i|n
                                                           c l u d emsi(mkeeTyy)p e|.|i nucplpuedreNsa(m'ej a=v=a=s ckreiyp)t '{)
                                                             | | 
                                                                   r emtiumrenT yvpael.uien;c
                                                                   l u d e s}(
                                                                   ' j s}o
                                                                   n ' )r
                                                                   e t u)r n{ 
                                                                   n u l l ;r
                                                                   e}t
                                                                   u
                                                                   r/n/  <MFoidleerCno d3eD  cfloalsdseNra mwei=t{h` $d{espiazretCmleansts }c otleoxrts-
                                                                   piunrtpelref-a5c0e0 `D}e p/a>r;t
                                                                   m e n}t
                                                                   F o lrdeetruPrrno p<sF i{l
                                                                   e   ccllaassssNNaammee=?{:` $s{tsriiznegC;l
                                                                   a s sp}r itmeaxrty-Cgorlaoyr-?4:0 0s`t}r i/n>g;;
                                                                   
                                                                   }  secondaryColor?: string;
                                                                     DepartmentIcon?: typeof Users;
                                                                     }
                                                                     
                                                                     export function DepartmentFolder({
                                                                       className,
                                                                         primaryColor = '#F59E0B',
                                                                           secondaryColor = '#FBBF24',
                                                                             DepartmentIcon
                                                                             }: DepartmentFolderProps) {
                                                                               return (
                                                                                   <div className={`relative ${className}`}>
                                                                                         <svg viewBox="0 0 64 64" className="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                                                                 {/* Shadow */}
                  <ellipse cx="32" cy="58" rx="24" ry="4" fill="black" opacity="0.1" />
          
            {/* Back panel with gradient */}
                  <defs>
                            <linearGradient id={`folder-grad-${primaryColor}`} x1="0%" y1="0%" x2="100%" y2="100%">
                                        <stop offset="0%" stopColor={secondaryColor} />
                                        <stop offset="100%" stopColor={primaryColor} />
                            </linearGradient>linearGradient>
                            <filter id="folder-shadow" x="-20%" y="-20%" width="140%" height="140%">
                                        <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.2" />
                            </filter>filter>
                  </defs>defs>
          
            {/* Back panel */}
                  <path
                              d="M6 16C6 13.7909 7.79086 12 10 12H24L30 18H54C56.2091 18 58 19.7909 58 22V50C58 52.2091 56.2091 54 54 54H10C7.79086 54 6 52.2091 6 50V16Z"
                              fill={primaryColor}
                              filter="url(#folder-shadow)"
                            />
          
            {/* Front panel with gradient */}
                  <path
                              d="M6 22C6 19.7909 7.79086 18 10 18H54C56.2091 18 58 19.7909 58 22V50C58 52.2091 56.2091 54 54 54H10C7.79086 54 6 52.2091 6 50V22Z"
                              fill={`url(#folder-grad-${primaryColor})`}
                            />
          
            {/* Top shine */}
                  <path
                              d="M10 18H54C56.2091 18 58 19.7909 58 22V24H6V22C6 19.7909 7.79086 18 10 18Z"
                              fill="white"
                              opacity="0.2"
                            />
          
            {/* Inner line detail */}
                  <path
                              d="M10 26H54"
                              stroke={primaryColor}
                              strokeWidth="1"
                              opacity="0.3"
                            />
          </svg>svg>
      
      {/* Department icon overlay */}
  {DepartmentIcon && (
            <div className="absolute inset-0 flex items-center justify-center pt-2">
                      <DepartmentIcon className="w-1/3 h-1/3 text-white/90 drop-shadow-sm" strokeWidth={1.5} />
            </div>div>
          )}
  </div>
    );
    }
  
  // Standard Windows-style filled folder icon
  function WindowsFolder({ className }: { className?: string }) {
      return (
      <svg viewBox="0 0 48 48" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Shadow */}
            <ellipse cx="24" cy="42" rx="16" ry="2" fill="black" opacity="0.1" />
      
        {/* Ba</svg>
