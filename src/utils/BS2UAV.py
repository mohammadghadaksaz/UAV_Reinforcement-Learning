import numpy as np
import matplotlib.pyplot as plt

class BS2UAV:
    def __init__(self, my_BS, my_UAV, B_W=5e8, ref_path_loss=61.34,\
                 num_path=10, f_c=28, path_loss=3.6, rep=100):
        self.my_UAV = my_UAV
        self.my_BS = my_BS
        self.noise_PSD = -174 + 10 * np.log10(B_W) 
        self.ref_path_loss = ref_path_loss
        self.num_path = num_path
        self.path_loss = path_loss
        self.PL_dB = 32.4 + 20 * np.log10(f_c)
        self.rep = rep

    def db2pow(self, pow_dB):
        return np.power(10, pow_dB/10)
    
    def generate_channel_1(self):
        ## claculate distance
        distance = np.sum((self.my_UAV.location - self.my_BS.location)**2, axis=1)**0.5
        ## slow-time varying angular information from BS
        mean_EAoD = self.my_BS.mean_EAoD
        sep_EAoD = self.my_BS.sep_EAoD
        mean_AAoD = self.my_BS.mean_AAoD
        sep_AAoD = self.my_BS.sep_AAoD
        ## slow-time varying angular information from UAV
        mean_EAoA = self.my_UAV.mean_EAoA
        sep_EAoA = self.my_UAV.sep_EAoA
        mean_AAoA = self.my_UAV.mean_AAoA
        sep_AAoA = self.my_UAV.sep_AAoA
        ## angles
        theta_t = (mean_EAoD + (2 * np.random.rand(self.num_path, 1) - 1) * sep_EAoD)
        phi_t = (mean_AAoD + (2 * np.random.rand(self.num_path, 1) - 1) * sep_AAoD)
        theta_r = (mean_EAoA + (2 * np.random.rand(self.num_path, 1) - 1) * sep_EAoA) 
        phi_r = (mean_AAoA + (2 * np.random.rand(self.num_path, 1) - 1) * sep_AAoA)
        ## Gamma
        gamma_xt = np.sin(theta_t * np.pi / 180.0) * np.cos(phi_t * np.pi / 180.0)
        gamma_yt = np.sin(theta_t * np.pi / 180.0) * np.sin(phi_t * np.pi / 180.0)
        gamma_xr = np.sin(theta_r * np.pi / 180.0) * np.cos(phi_r * np.pi / 180.0)
        gamma_yr = np.sin(theta_r * np.pi / 180.0) * np.sin(phi_r * np.pi / 180.0)
        ## # of antennas from BS
        M_Tx = int(np.sqrt(self.my_BS.N_T))
        M_Ty = int(np.sqrt(self.my_BS.N_T))
        ## A_T
        n_x = np.arange(0, M_Tx, dtype=int)
        n_y = np.arange(0, M_Ty, dtype=int)
        [n_x, n_y] = np.meshgrid(n_x, n_y)
        n_x = (n_x.flatten(order='F')).transpose()
        n_y = (n_y.flatten(order='F')).transpose()
        A_T = np.exp(-1j * np.pi * ((gamma_xt * n_x) + (gamma_yt * n_y)))
        ## # of antennas from BS
        M_Rx = int(np.sqrt(self.my_UAV.N_r))
        M_Ry = int(np.sqrt(self.my_UAV.N_r))
        ## A_R
        n_x = np.arange(0, M_Rx, dtype=int)
        n_y = np.arange(0, M_Ry, dtype=int)
        [n_x, n_y] = np.meshgrid(n_x, n_y)
        n_x = (n_x.flatten(order='F')).transpose()
        n_y = (n_y.flatten(order='F')).transpose()
        A_R = (np.exp(-1j * np.pi * ((gamma_xr * n_x) + (gamma_yr * n_y)))).transpose()
        ## path_gain
        D = np.random.rand(1, self.num_path) * distance
        PL = self.db2pow(-self.PL_dB) * np.diag((D ** (-self.path_loss))[0])
        Z = np.sqrt(1 / (2 * self.num_path)) * (np.random.randn(1, self.num_path) + 1j * np.random.randn(1, self.num_path))
        Z = np.diag(Z[0])
        Z = np.sqrt(PL) @ Z
        ## channel
        H_1 = A_R @ Z @ A_T
        ## return phase and channel
        return H_1, A_R, A_T
    
    def full_CSI(self):
        [H_1, A_R, A_T] = self.generate_channel_1()
        [U_1, S_1, V_H] = np.linalg.svd(H_1)
        N_s = self.my_BS.N_s
        V_1 = V_H.conj().T
        S_val = np.diag(S_1)
        PL = np.sum(np.square(S_1[0:N_s])) / np.sum(np.square(S_1))
        U_1 = U_1[:, 0:N_s]
        V_1 = V_1[:, 0:N_s]
        S_1 = S_val[0:N_s, 0: N_s]
        return H_1, U_1, V_1
    
    def low_CSI(self, H_1, F_b, F_ur):
        # H_eff_1 = F_b* @ H_1 @ F_ut
        H_eff_1 = F_ur @ H_1 @ F_b
        N_s = self.my_BS.N_s
        # SVD
        [U_eff_1, S_eff_1, VH_eff_1] = np.linalg.svd(H_eff_1)
        V_eff_1 = VH_eff_1.conj().T
        S_val_eff = np.diag(S_eff_1)
        PL_eff = np.sum(S_eff_1[0:N_s] ** 2) / np.sum(S_eff_1 ** 2)
        U_eff_1 = U_eff_1[:, 0:N_s]
        V_eff_1 = V_eff_1[:, 0:N_s]
        S_eff_1 = S_val_eff[0:N_s, 0: N_s]
        return H_eff_1, U_eff_1, V_eff_1  
    
    def f_HBF_EQ(self, H_eff_1, U_eff_1, V_eff_1):
        # Transmit/Noise NoisePower_dBm
        P_t = self.db2pow(self.my_BS.P_t - 30)
        NoisePower_1 = self.db2pow(self.noise_PSD - 30)
        # Number of Streams
        N_S_1 = np.size(V_eff_1, 1)
        # FDP/FDC
        B_b = self.my_BS.calc_b_b(P_t, N_S_1, V_eff_1)
        B_ur = self.my_UAV.calc_b_ur(U_eff_1)
        # Transformed Channel
        H_coded_1 = B_ur @ H_eff_1 @ B_b
        # Desired Signal
        SignalPower_1 = np.abs(np.diag(H_coded_1)) ** 2
        # Interference Signal
        InterPower_1 = np.sum(np.abs(H_coded_1 - np.diag(np.diag(H_coded_1))) ** 2, axis=1)
        # Capacity with Equal PA
        C_HBF = np.sum(np.log2(1 + (SignalPower_1 / (NoisePower_1 + InterPower_1))))
        return C_HBF    
    
    def f_SU_MIMO_Cap(self):
        C_HBF = np.zeros(self.rep)
        F_T = self.my_BS.f_b
        F_R = self.my_UAV.f_ur
        for i in range(self.rep):
            # Full CSI
            [H, U, V] = self.full_CSI()
            # Effective CSI
            [H_eff, U_eff, V_eff] = self.low_CSI(H, F_T, F_R)
            # Digital Beamforming
            C_HBF[i] = self.f_HBF_EQ(H_eff, U_eff, V_eff)
        C_1 = (1 / 2) * np.mean(C_HBF)
        return C_1
    

    def plot_BS2UAV(self, n_steps=10, n_levels=10, x_min=0,
                            x_max=100, y_min=0, y_max=100,\
                                file_path="figs"):
            
            x = np.linspace(x_min, x_max, n_steps)
            y = np.linspace(y_min, y_max, n_steps)
            X, Y = np.meshgrid(x, y)
            Rate = np.zeros((n_steps, n_steps))

            for i in range(n_steps):
                for j in range(n_steps):
                    self.my_UAV.set_location(x[i], y[j])
                    Rate[i, j] = self.f_SU_MIMO_Cap()

            plt.contourf(Y, X, Rate, levels=n_levels)
            plt.colorbar(label='Achievable Rate [bps/Hz]')
            plt.xlabel('X')
            plt.ylabel('Y')
            plt.savefig("figs/BS2UAV.pdf")
            plt.show()


if __name__ == "__main__": 

    from src.components.UAV import UAV
    from src.components.BS import BS

    my_UAV = UAV()
    my_BS = BS()
    my_BS2UAV = BS2UAV(my_BS, my_UAV)
    my_BS2UAV.plot_BS2UAV()
    
